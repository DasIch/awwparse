# coding: utf-8
"""
    awwparse.testsuite.init
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from awwparse import (
    Option, Bytes, Command, Last, List, Arguments, Argument, CLI
)
from awwparse.utils import missing
from awwparse.exceptions import (
    ArgumentMissing, CommandMissing, OptionConflict, CommandConflict,
    UnexpectedArgument
)
from awwparse.testsuite import TestCase, make_suite


def make_command(options=None, commands=None, command_cls=Command):
    return type("TestCommand", (command_cls, ), {
        "options": {} if options is None else options,
        "commands": {} if commands is None else commands,
        "main": lambda self, **kwargs: kwargs
    })()


class OptionTestCase(TestCase):
    def test_type_container(self):
        class TestOption(Option):
            container_type = List

        command = make_command({"foo": TestOption("a", Bytes())})
        self.assert_equal(
            command.run(["-a", "foo", "-a", "bar"]),
            {"foo": ["foo", "bar"]}
        )

    def test_signature(self):
        command = make_command({"option": Option("o", Bytes(), Bytes(), Bytes())})
        for args in [["-o"], ["-o", "foo"], ["-o", "foo", "bar"]]:
            with self.assert_raises(ArgumentMissing):
                command.run(args)

        command = make_command({"option": Option("o", Bytes(), [Bytes(), Bytes()])})
        self.assert_equal(command.run(["-o", "a"]), {"option": ["a"]})
        self.assert_equal(
            command.run(["-o", "a", "b", "c"]),
            {"option": ["a", "b", "c"]}
        )
        for args in [["-o"], ["-o", "a", "b"]]:
            with self.assert_raises(ArgumentMissing):
                command.run(args)

        command = make_command({
            "option": Option("o", Bytes(), [Bytes(), [Bytes()]])
        })
        args = ["-o", "a", "b", "c"]
        for i in xrange(2, len(args) + 1):
            self.assert_equal(
                command.run(args[:i]),
                {"option": args[1:i] or [missing]}
            )

    def test_default(self):
        command = make_command({"option": Option("o", Bytes())})
        self.assert_equal(command.options["option"].default, missing)
        self.assert_equal(command.run([]), {})

        command = make_command(
            {"option": Option("o", Bytes(default="foobar"))}
        )
        self.assert_equal(command.options["option"].default, "foobar")
        self.assert_equal(command.run([]), {"option": "foobar"})

    def test_get_usage(self):
        option = Option("a", Bytes(metavar="foo"))
        self.assert_equal(option.get_usage(), "-a foo")
        self.assert_equal(option.get_usage(short=False), "-a foo")

        option = Option("abc", Bytes(metavar="foo"))
        self.assert_equal(option.get_usage(), "--abc foo")
        self.assert_equal(option.get_usage(short=False), "--abc foo")

        option = Option("a", "abc", Bytes(metavar="foo"))
        self.assert_equal(option.get_usage(), "-a foo")
        self.assert_equal(option.get_usage(short=False), "--abc foo")

        option = Option("a", Bytes())
        self.assert_equal(option.get_usage(), "-a a")
        self.assert_equal(option.get_usage(metavar="foo"), "-a foo")

    def test_abbreviation_prefix(self):
        command = make_command({"option": Option("o", Bytes())})
        self.assert_equal(command.options["option"].abbreviation_prefix, "-")
        self.assert_(command.options["option"].matches("-o"))

        command = make_command({
            "option": Option("o", Bytes(), abbreviation_prefix="+")
        })
        self.assert_equal(command.options["option"].abbreviation_prefix, "+")
        self.assert_(command.options["option"].matches("+o"))
        self.assert_equal(command.run(["+o", "foo"]), {"option": "foo"})

    def test_name_prefix(self):
        command = make_command({"option": Option("option", Bytes())})
        self.assert_equal(command.options["option"].name_prefix, "--")
        self.assert_(command.options["option"].matches("--option"))

        command = make_command({
            "option": Option("option", Bytes(), name_prefix="++")
        })
        self.assert_equal(command.options["option"].name_prefix, "++")
        self.assert_(command.options["option"].matches("++option"))
        self.assert_equal(command.run(["++option", "foo"]), {"option": "foo"})

    def test_matches(self):
        option = Option("o", "option", Bytes())
        self.assert_equal(option.matches("-a"), (False, "-a"))
        self.assert_equal(option.matches("-o"), (True, ""))
        self.assert_equal(option.matches("--asd"), (False, "--asd"))
        self.assert_equal(option.matches("--option"), (True, ""))

    def test_repr(self):
        self.assert_(
            repr(Option("o", Bytes())).startswith("Option('o', Last")
        )
        self.assert_(
            repr(Option("option", Bytes())).startswith("Option('option', Last")
        )
        signature = Last(Bytes())
        self.assert_equal(
            repr(Option("o", "option", signature)),
            "Option('o', 'option', %r, abbreviation_prefix='-', name_prefix='--', help=None)" % signature
        )


class CommandTestCase(TestCase):
    def test_option_shorts_and_longs(self):
        command = Command()
        command.add_option("foo", Option("a", Bytes()))
        command.add_option("bar", Option("abc", Bytes()))
        self.assert_not_in(None, command.option_shorts)
        self.assert_not_in(None, command.option_longs)

    def test_get_usage(self):
        command = Command()
        command.add_option("foo", Option("o", Bytes()))
        self.assert_equal(command.usage, "[-o foo]")

        command.add_command("bar", Command())
        self.assert_equal(command.usage, "[-o foo] {bar}")

        command.add_argument(Argument(Bytes(), "baz"))
        self.assert_equal(command.usage, "[-o foo] {bar} baz")

    def test_add_option(self):
        command = Command()
        a = Option("a", "foobar", Bytes())
        command.add_option("foo", a)
        with self.assert_raises(OptionConflict):
            command.add_option("bar", a)
        with self.assert_raises(OptionConflict):
            command.add_option("baz", Option("foobar", Bytes()))
        with self.assert_raises(OptionConflict):
            command.add_option("foo", Option("something", Bytes()))
        command.add_option("foo", Option("something", Bytes()), force=True)
        self.assert_equal(command.options["foo"].name, "something")

    def test_add_command(self):
        command = Command()
        command.add_command("foobar", Command())
        command.add_command("foobar", Command(), force=True)
        with self.assert_raises(CommandConflict):
            command.add_command("foobar", Command())

    def test_run(self):
        class TestCommand(Command):
            commands = {"foo": Command()}
        with self.assert_raises(CommandMissing):
            TestCommand().run([])

        with self.assert_raises(NotImplementedError):
            Command().run([])

        with self.assert_raises(UnexpectedArgument):
            Command().run(["--unexpected"])

        with self.assert_raises(UnexpectedArgument):
            Command().run(["-u"])

        with self.assert_raises(UnexpectedArgument):
            Command().run(["unexpected"])

        command = Command()
        command.add_option("foo", Option("b", Bytes()))
        with self.assert_raises(UnexpectedArgument):
            command.run(["-a"])

    def test_main(self):
        class TestCommand(Command):
            options = {
                "foo": Option("a", Bytes()),
                "bar": Option("b", Bytes())
            }

            def main(self, foo, bar):
                assert foo == "foo"
                assert bar == "bar"
        TestCommand().run(["-a", "foo", "-b", "bar"])

    def test_multiple_abbreviations(self):
        command = make_command({
            "a": Option("a", Bytes()),
            "b": Option("b", Bytes()),
            "c": Option("c", Bytes())
        })
        self.assert_equal(
            command.run(["-abc", "foo", "bar", "baz"]),
            {"a": "foo", "b": "bar", "c": "baz"}
        )

    def test_subcommands(self):
        results = []
        class A(Command):
            def main(self):
                results.append("a")

        class B(Command):
            def main(self):
                results.append("b")

        class C(Command):
            commands = {"a": A(), "b": B()}

        C().run(["a"])
        self.assert_equal(results, ["a"])
        C().run(["b"])
        self.assert_equal(results, ["a", "b"])

    def test_option_inheritance(self):
        class A(Command):
            def main(self, **kwargs):
                assert "foo" in kwargs
                assert kwargs["foo"] == "bar"

        class B(Command):
            options = {"foo": Option("a", Bytes())}
            commands = {"spam": A()}

        B().run(["-a", "bar", "spam"])

    def test_arguments(self):
        class TestCommand(Command):
            arguments = Argument(Bytes(), "foo")

            def main(self, foo):
                assert foo == "foo"

        TestCommand().run(["foo"])

        class TestCommand(Command):
            arguments = Argument(Bytes(), "foo"), Argument(Bytes(), "bar")

            def main(self, foo, bar):
                assert foo == "foo"
                assert bar == "bar"

        with self.assert_raises(ArgumentMissing):
            TestCommand().run(["foo"])


class ArgumentsTestCase(TestCase):
    def test_rewind(self):
        arguments = Arguments(["foo", "bar"])
        self.assert_equal(arguments.next(), "foo")
        self.assert_equal(arguments.trace, ["foo"])
        arguments.rewind()
        self.assert_equal(arguments.trace, [])
        self.assert_equal(arguments.next(), "foo")

    def test_repr(self):
        args = iter(["foo", "bar"])
        arguments = Arguments(args)
        self.assert_equal(
            repr(arguments),
            "<Arguments(%r) []>" % args
        )
        arguments.next()
        self.assert_equal(
            repr(arguments),
            "<Arguments(%r) ['foo']>" % args
        )


class ArgumentTestCase(TestCase):
    def test_usage(self):
        self.assert_equal(Argument(Bytes(), "foo").usage, "foo")
        self.assert_equal(
            Argument(Bytes(), "foo", optional=True).usage,
            "[foo]"
        )
        self.assert_equal(
            Argument(Bytes(), "foo", remaining=True).usage,
            "[foo ...]"
        )

    def test_repr(self):
        bytes = Bytes()
        argument = Argument(bytes, "foo")
        self.assert_equal(
            repr(argument),
            "Argument(%r, 'foo', help=None)" % bytes
        )


class CLITestCase(TestCase):
    def test_usage(self):
        cli = CLI(application_name="spam")
        cli.add_argument(Argument(Bytes(), "foo"))
        self.assert_equal(cli.usage, "spam foo")

        cli.usage = "blubb"
        self.assert_equal(cli.usage, "blubb")


suite = make_suite([
    OptionTestCase, CommandTestCase, ArgumentsTestCase, ArgumentTestCase,
    CLITestCase
])
