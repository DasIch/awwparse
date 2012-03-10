# coding: utf-8
"""
    awwparse.testsuite.init
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from awwparse import store, append, add, CLI, Option, Bytes, Command
from awwparse.utils import missing
from awwparse.exceptions import ArgumentMissing, CommandMissing
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


def make_cli(options):
    return type("TestCLI", (CLI, ), {
        "options": options,
        "main": lambda self, **kwargs: kwargs
    })


class OptionTestCase(TestCase):
    def test_signature(self):
        cli = make_cli({"option": Option("o", Bytes(), Bytes(), Bytes())})()
        for args in [["-o"], ["-o", "foo"], ["-o", "foo", "bar"]]:
            with self.assert_raises(ArgumentMissing):
                cli.run(args)

        cli = make_cli({"option": Option("o", Bytes(), [Bytes(), Bytes()])})()
        self.assert_(cli.options["option"].types[1].optional)
        self.assert_equal(cli.run(["-o", "a"]), {"option": ["a"]})
        self.assert_equal(
            cli.run(["-o", "a", "b", "c"]),
            {"option": ["a", "b", "c"]}
        )
        for args in [["-o"], ["-o", "a", "b"]]:
            with self.assert_raises(ArgumentMissing):
                cli.run(args)

        cli = make_cli({
            "option": Option("o", Bytes(), [Bytes(), [Bytes()]])
        })()
        self.assert_(
            all(type.optional for type in cli.options["option"].types[1:])
        )
        args = ["-o", "a", "b", "c"]
        for i in xrange(2, len(args) + 1):
            self.assert_equal(
                cli.run(args[:i]),
                {"option": args[1:i] or [missing]}
            )

    def test_default(self):
        cli = make_cli({"option": Option("o", Bytes())})()
        self.assert_equal(cli.options["option"].default, missing)
        self.assert_equal(cli.run([]), {})

        cli = make_cli({"option": Option("o", Bytes(default="foobar"))})()
        self.assert_equal(cli.options["option"].default, "foobar")
        self.assert_equal(cli.run([]), {"option": "foobar"})

    def test_abbreviation_prefix(self):
        cli = make_cli({"option": Option("o", Bytes())})()
        self.assert_equal(cli.options["option"].abbreviation_prefix, "-")
        self.assert_(cli.options["option"].matches("-o"))

        cli = make_cli({
            "option": Option("o", Bytes(), abbreviation_prefix="+")
        })()
        self.assert_equal(cli.options["option"].abbreviation_prefix, "+")
        self.assert_(cli.options["option"].matches("+o"))
        self.assert_equal(cli.run(["+o", "foo"]), {"option": "foo"})

    def test_name_prefix(self):
        cli = make_cli({"option": Option("option", Bytes())})()
        self.assert_equal(cli.options["option"].name_prefix, "--")
        self.assert_(cli.options["option"].matches("--option"))

        cli = make_cli({
            "option": Option("option", Bytes(), name_prefix="++")
        })()
        self.assert_equal(cli.options["option"].name_prefix, "++")
        self.assert_(cli.options["option"].matches("++option"))
        self.assert_equal(cli.run(["++option", "foo"]), {"option": "foo"})

    def test_actions(self):
        cli = make_cli({"option": Option("o", Bytes())})()
        self.assert_equal(cli.run(["-o", "foobar"]), {"option": "foobar"})
        self.assert_equal(
            cli.run(["-o", "foo", "-o", "bar"]),
            {"option": "bar"}
        )

        cli = make_cli({"option": Option("o", Bytes(), action=append)})()
        self.assert_equal(cli.run(["-o", "foobar"]), {"option": ["foobar"]})
        self.assert_equal(
            cli.run(["-o", "foo", "-o", "bar"]),
            {"option": ["foo", "bar"]}
        )

    def test_matches(self):
        option = Option("o", "option", Bytes())
        self.assert_equal(option.matches("-a"), (False, "-a"))
        self.assert_equal(option.matches("-o"), (True, ""))
        self.assert_equal(option.matches("--asd"), (False, "--asd"))
        self.assert_equal(option.matches("--option"), (True, ""))


class CLITestCase(TestCase):
    def test_run(self):
        class TestCLI(CLI):
            commands = {"foo": Command()}
        test_cli = TestCLI()
        with self.assert_raises(CommandMissing):
            test_cli.run([])

        with self.assert_raises(NotImplementedError):
            CLI().run([])

    def test_multiple_abbreviations(self):
        cli = make_cli({
            "a": Option("a", Bytes()),
            "b": Option("b", Bytes()),
            "c": Option("c", Bytes())
        })()
        self.assert_equal(
            cli.run(["-abc", "foo", "bar", "baz"]),
            {"a": "foo", "b": "bar", "c": "baz"}
        )


suite = make_suite([ActionTestCase, OptionTestCase, CLITestCase])
