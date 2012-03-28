# coding: utf-8
"""
    awwparse.testsuite.init
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
try:
    from io import StringIO
except ImportError:
    from StringIO import StringIO

import six

from awwparse import (
    Option, Command, Last, List, Arguments, Argument, CLI, Integer,
    String
)
from awwparse.utils import missing
from awwparse.exceptions import (
    ArgumentMissing, CommandMissing, OptionConflict, CommandConflict,
    UnexpectedArgument, PositionalArgumentMissing, UserTypeError
)
from awwparse.testsuite import TestCase, make_suite


def make_command(options=None, commands=None, command_cls=Command):
    def main(self, **kwargs):
        return kwargs
    return type("TestCommand", (command_cls, ), {
        "options": {} if options is None else options,
        "commands": {} if commands is None else commands,
        "main": main
    })()


class OptionTestCase(TestCase):
    def test_type_container(self):
        class TestOption(Option):
            container_type = List

        command = make_command({"foo": TestOption("a", String())})
        self.assert_equal(
            command.run(["-a", "foo", "-a", "bar"]),
            {"foo": [six.u("foo"), six.u("bar")]}
        )

    def test_signature(self):
        command = make_command({"option": Option("o", String(), String(), String())})
        for args in [["-o"], ["-o", "foo"], ["-o", "foo", "bar"]]:
            with self.assert_raises(ArgumentMissing):
                command.run(args, passthrough_errors=True)

        command = make_command({"option": Option("o", String(), [String(), String()])})
        self.assert_equal(command.run(["-o", "a"]), {"option": [six.u("a")]})
        self.assert_equal(
            command.run(["-o", "a", "b", "c"]),
            {"option": ["a", "b", "c"]}
        )
        for args in [["-o"], ["-o", "a", "b"]]:
            with self.assert_raises(ArgumentMissing):
                command.run(args, passthrough_errors=True)

        command = make_command({
            "option": Option("o", String(), [String(), [String()]])
        })
        args = ["-o", "a", "b", "c"]
        for i in range(2, len(args) + 1):
            self.assert_equal(
                command.run(args[:i]),
                {"option": args[1:i] or [missing]}
            )

    def test_default(self):
        command = make_command({"option": Option("o", String())})
        self.assert_equal(command.options["option"].default, missing)
        self.assert_equal(command.run([]), {})

        command = make_command(
            {"option": Option("o", String(default="foobar"))}
        )
        self.assert_equal(command.options["option"].default, "foobar")
        self.assert_equal(command.run([]), {"option": "foobar"})

    def test_get_usage(self):
        option = Option("a", String(metavar="foo"))
        self.assert_equal(option.get_usage(), "-a foo")
        self.assert_equal(option.get_usage(using="long"), "-a foo")
        self.assert_equal(option.get_usage(using="both"), "-a foo")

        option = Option("a", "abc", String(metavar="foo"))
        self.assert_equal(option.get_usage(), "-a foo")
        self.assert_equal(option.get_usage(using="long"), "--abc foo")
        self.assert_equal(option.get_usage(using="both"), "-a, --abc foo")

    def test_abbreviation_prefix(self):
        command = make_command({"option": Option("o", String())})
        self.assert_equal(command.options["option"].abbreviation_prefix, "-")
        self.assert_true(command.options["option"].matches("-o"))

        command = make_command({
            "option": Option("o", String(), abbreviation_prefix="+")
        })
        self.assert_equal(command.options["option"].abbreviation_prefix, "+")
        self.assert_true(command.options["option"].matches("+o"))
        self.assert_equal(command.run(["+o", "foo"]), {"option": six.u("foo")})

    def test_name_prefix(self):
        command = make_command({"option": Option("option", String())})
        self.assert_equal(command.options["option"].name_prefix, "--")
        self.assert_true(command.options["option"].matches("--option"))

        command = make_command({
            "option": Option("option", String(), name_prefix="++")
        })
        self.assert_equal(command.options["option"].name_prefix, "++")
        self.assert_true(command.options["option"].matches("++option"))
        self.assert_equal(
            command.run(["++option", "foo"]),
            {"option": six.u("foo")}
        )

    def test_matches(self):
        option = Option("o", "option", String())
        self.assert_equal(option.matches("-a"), (False, "-a"))
        self.assert_equal(option.matches("-o"), (True, ""))
        self.assert_equal(option.matches("--asd"), (False, "--asd"))
        self.assert_equal(option.matches("--option"), (True, ""))

    def test_repr(self):
        self.assert_true(
            repr(Option("o", String())).startswith("Option('o', Last")
        )
        self.assert_true(
            repr(Option("option", String())).startswith("Option('option', Last")
        )
        signature = Last(String())
        self.assert_equal(
            repr(Option("o", "option", signature)),
            "Option('o', 'option', %r, abbreviation_prefix='-', name_prefix='--', help=None)" % signature
        )


class CommandTestCase(TestCase):
    def test_option_shorts_and_longs(self):
        command = Command()
        command.add_option("foo", Option("a", String()))
        command.add_option("bar", Option("abc", String()))
        self.assert_not_in(None, command.option_shorts)
        self.assert_not_in(None, command.option_longs)

    def test_get_usage(self):
        command = Command()
        command.add_option("foo", Option("o", String()))
        self.assert_equal(command.get_usage(), "[-o foo]")

        command.add_command("bar", Command())
        self.assert_equal(command.get_usage(), "[-o foo] {bar}")

        command.add_argument(Argument(String(), "baz"))
        self.assert_equal(command.get_usage(), "[-o foo] {bar} baz")

    def test_add_option(self):
        command = Command()
        a = Option("a", "foobar", String())
        command.add_option("foo", a)
        with self.assert_raises(OptionConflict):
            command.add_option("bar", a)
        with self.assert_raises(OptionConflict):
            command.add_option("baz", Option("foobar", String()))
        with self.assert_raises(OptionConflict):
            command.add_option("foo", Option("something", String()))
        command.add_option("foo", Option("something", String()), force=True)
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
            TestCommand().run([], passthrough_errors=True)

        with self.assert_raises(NotImplementedError):
            Command().run([], passthrough_errors=True)

        with self.assert_raises(UnexpectedArgument):
            Command().run(["--unexpected"], passthrough_errors=True)

        with self.assert_raises(UnexpectedArgument):
            Command().run(["-u"], passthrough_errors=True)

        with self.assert_raises(UnexpectedArgument):
            Command().run(["unexpected"], passthrough_errors=True)

        command = Command()
        command.add_option("foo", Option("b", String()))
        with self.assert_raises(UnexpectedArgument):
            command.run(["-a"], passthrough_errors=True)

    def test_main(self):
        class TestCommand(Command):
            options = {
                "foo": Option("a", String()),
                "bar": Option("b", String())
            }

            def main(self, foo, bar):
                assert foo == six.u("foo")
                assert bar == six.u("bar")
        TestCommand().run(["-a", "foo", "-b", "bar"])

    def test_multiple_abbreviations(self):
        command = make_command({
            "a": Option("a", String()),
            "b": Option("b", String()),
            "c": Option("c", String())
        })
        self.assert_equal(
            command.run(["-abc", "foo", "bar", "baz"]),
            {"a": six.u("foo"), "b": six.u("bar"), "c": six.u("baz")}
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
                assert kwargs["foo"] == six.u("bar")

        class B(Command):
            options = {"foo": Option("a", String())}
            commands = {"spam": A()}

        B().run(["-a", "bar", "spam"])

    def test_arguments(self):
        class TestCommand(Command):
            arguments = Argument(String(), "foo")

            def main(self, foo):
                assert foo == six.u("foo")

        TestCommand().run(["foo"])

        class TestCommand(Command):
            arguments = Argument(String(), "foo"), Argument(String(), "bar")

            def main(self, foo, bar):
                assert foo == "foo"
                assert bar == "bar"

        with self.assert_raises(PositionalArgumentMissing):
            TestCommand().run(["foo"], passthrough_errors=True)


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
        self.assert_equal(Argument(String(), "foo").usage, "foo")
        self.assert_equal(
            Argument(String(), "foo", optional=True).usage,
            "[foo]"
        )
        self.assert_equal(
            Argument(String(), "foo", remaining=True).usage,
            "[foo ...]"
        )

    def test_repr(self):
        bytes = String()
        argument = Argument(bytes, "foo")
        self.assert_equal(
            repr(argument),
            "Argument(%r, 'foo', help=None)" % bytes
        )


class CLITestCase(TestCase):
    def test_get_usage(self):
        cli = CLI(application_name="spam")
        cli.add_argument(Argument(String(), "foo"))
        self.assert_equal(cli.get_usage(), "spam foo")

        cli.usage = "blubb"
        self.assert_equal(cli.get_usage(), "blubb")

    def test_print_usage(self):
        stringio = StringIO()
        cli = CLI(
            usage=("foobarbaz " * 20).strip(), width=80,
            stdout=stringio
        )
        cli.print_usage()
        self.assert_equal(
            stringio.getvalue(),
            ("Usage: foobarbaz foobarbaz foobarbaz foobarbaz foobarbaz foobarbaz foobarbaz\n"
             "       foobarbaz foobarbaz foobarbaz foobarbaz foobarbaz foobarbaz foobarbaz\n"
             "       foobarbaz foobarbaz foobarbaz foobarbaz foobarbaz foobarbaz\n"
            )
        )

    def test_print_help(self):
        stringio = StringIO()
        cli = CLI(application_name="app", stdout=stringio)
        cli.add_argument(Argument(String(), "foo"))
        cli.print_help()
        self.assert_equal(stringio.getvalue(), (
            "Usage: app foo\n"
            "\n"
            "Positional Arguments\n"
            "  foo\n"
        ))

        cli.stdout = stringio = StringIO()
        cli.add_option("bar", Option("a", String()))
        cli.print_help()
        self.assert_equal(stringio.getvalue(), (
            "Usage: app [-a bar] foo\n"
            "\n"
            "Positional Arguments\n"
            "  foo\n"
            "\n"
            "Options\n"
            "  -a bar\n"
        ))

        cli.stdout = stringio = StringIO()
        cli.add_command("baz", Command())
        cli.print_help()
        self.assert_equal(stringio.getvalue() , (
            "Usage: app [-a bar] {baz} foo\n"
            "\n"
            "Positional Arguments\n"
            "  foo\n"
            "\n"
            "Options\n"
            "  -a bar\n"
            "\n"
            "Commands\n"
            "  baz\n"
        ))

    def test_error_handling(self):
        class TestCLI(CLI):
            def main(self, *args, **kwargs):
                return args, kwargs
        stringio = StringIO()
        def exit(code):
            assert code != 1
        cli = TestCLI(
            application_name="app", stdout=stringio, stderr=stringio, exit=exit
        )
        cli.add_option("foo", Option("o", Integer()))
        with self.assert_raises(AssertionError) as error:
            cli.run(["-o", "foo"])
        self.assert_equal(
            error.exception.args[0], "exit should have aborted execution"
        )
        self.assert_equal(
            stringio.getvalue(),
            (
                "Error: 'foo' is not an integer\n"
                "Usage: app [-o foo]\n"
                "\n"
                "Options\n"
                "  -o foo\n"
            )
        )
        with self.assert_raises(UserTypeError):
            cli.run(["-o", "foo"], passthrough_errors=True)

        stringio = StringIO()
        cli = TestCLI(
            application_name="app", stdout=stringio, stderr=stringio, exit=exit
        )
        command = Command()
        command.add_option("foo", Option("o", String()))
        cli.add_command("spam", command)
        with self.assert_raises(AssertionError) as error:
            cli.run(["spam", "-o"])
        self.assert_equal(
            error.exception.args[0],
            "exit should have aborted execution"
        )
        self.assert_equal(
            stringio.getvalue(),
            (
                "Error: foo\n"
                "Usage: app spam [-o foo]\n"
                "\n"
                "Options\n"
                "  -o foo\n"
            )
        )


suite = make_suite([
    OptionTestCase, CommandTestCase, ArgumentsTestCase, ArgumentTestCase,
    CLITestCase
])
