# coding: utf-8
"""
    awwparse.testsuite.init
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from awwparse import store, append, add, Option, Bytes, Command
from awwparse.utils import missing
from awwparse.exceptions import (
    ArgumentMissing, CommandMissing, OptionConflict, CommandConflict,
    UnexpectedArgument
)
from awwparse.testsuite import TestCase, make_suite


class ActionTestCase(TestCase):
    def test_store(self):
        self.assert_equal(store({}, "foo", "bar"), {"foo": "bar"})

    def test_append(self):
        namespace = {}
        self.assert_equal(append(namespace, "foo", "spam"), {"foo": ["spam"]})
        self.assert_equal(
            append(namespace, "foo", "eggs"),
            {"foo": ["spam", "eggs"]}
        )

    def test_add(self):
        namespace = {}
        self.assert_equal(add(namespace, "foo", "spam"), {"foo": {"spam"}})
        self.assert_equal(
            add(namespace, "foo", "eggs"),
            {"foo": {"spam", "eggs"}}
        )


def make_command(options=None, commands=None, command_cls=Command):
    return type("TestCommand", (command_cls, ), {
        "options": {} if options is None else options,
        "commands": {} if commands is None else commands,
        "main": lambda self, **kwargs: kwargs
    })()


class OptionTestCase(TestCase):
    def test_signature(self):
        command = make_command({"option": Option("o", Bytes(), Bytes(), Bytes())})
        for args in [["-o"], ["-o", "foo"], ["-o", "foo", "bar"]]:
            with self.assert_raises(ArgumentMissing):
                command.run(args)

        command = make_command({"option": Option("o", Bytes(), [Bytes(), Bytes()])})
        self.assert_(command.options["option"].types[1].optional)
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
        self.assert_(
            all(type.optional for type in command.options["option"].types[1:])
        )
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

    def test_actions(self):
        command = make_command({"option": Option("o", Bytes())})
        self.assert_equal(command.run(["-o", "foobar"]), {"option": "foobar"})
        self.assert_equal(
            command.run(["-o", "foo", "-o", "bar"]),
            {"option": "bar"}
        )

        command = make_command({"option": Option("o", Bytes(), action=append)})
        self.assert_equal(command.run(["-o", "foobar"]), {"option": ["foobar"]})
        self.assert_equal(
            command.run(["-o", "foo", "-o", "bar"]),
            {"option": ["foo", "bar"]}
        )

    def test_matches(self):
        option = Option("o", "option", Bytes())
        self.assert_equal(option.matches("-a"), (False, "-a"))
        self.assert_equal(option.matches("-o"), (True, ""))
        self.assert_equal(option.matches("--asd"), (False, "--asd"))
        self.assert_equal(option.matches("--option"), (True, ""))

    def test_repr(self):
        self.assert_(
            repr(Option("o", Bytes())).startswith("Option('o', Bytes")
        )
        self.assert_(
            repr(Option("option", Bytes())).startswith("Option('option', Bytes")
        )
        self.assert_equal(
            repr(Option("o", "option", Bytes())),
            "Option('o', 'option', %r, abbreviation_prefix='-', name_prefix='--', action='store')" % Bytes()
        )


class CommandTestCase(TestCase):
    def test_option_shorts_and_longs(self):
        command = Command()
        command.add_option("foo", Option("a", Bytes()))
        command.add_option("bar", Option("abc", Bytes()))
        self.assert_not_in(None, command.option_shorts)
        self.assert_not_in(None, command.option_longs)

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


suite = make_suite([ActionTestCase, OptionTestCase, CommandTestCase])
