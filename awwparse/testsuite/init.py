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
    options.setdefault("main", lambda self, **kwargs: kwargs)
    return CLI.__metaclass__("TestCLI", (CLI, ), options)


class OptionTestCase(TestCase):
    def test_signature(self):
        cli = make_cli({"option": Option("o", Bytes(), Bytes(), Bytes())})()
        for args in [["-o"], ["-o", "foo"], ["-o", "foo", "bar"]]:
            with self.assert_raises(ArgumentMissing):
                cli.run(args)

        cli = make_cli({"option": Option("o", Bytes(), [Bytes(), Bytes()])})()
        self.assert_(cli.option.types[1].optional)
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
        self.assert_(all(type.optional for type in cli.option.types[1:]))
        args = ["-o", "a", "b", "c"]
        for i in xrange(2, len(args) + 1):
            self.assert_equal(
                cli.run(args[:i]),
                {"option": args[1:i] or [missing]}
            )

    def test_default(self):
        cli = make_cli({"option": Option("o", Bytes())})()
        self.assert_equal(cli.option.default, missing)
        self.assert_equal(cli.run([]), {})

        cli = make_cli({"option": Option("o", Bytes(default="foobar"))})()
        self.assert_equal(cli.option.default, "foobar")
        self.assert_equal(cli.run([]), {"option": "foobar"})

    def test_abbreviation_prefix(self):
        cli = make_cli({"option": Option("o", Bytes())})()
        self.assert_equal(cli.option.abbreviation_prefix, "-")
        self.assert_(cli.option.matches("-o"))

        cli = make_cli({
            "option": Option("o", Bytes(), abbreviation_prefix="+")
        })()
        self.assert_equal(cli.option.abbreviation_prefix, "+")
        self.assert_(cli.option.matches("+o"))
        self.assert_equal(cli.run(["+o", "foo"]), {"option": "foo"})

    def test_name_prefix(self):
        cli = make_cli({"option": Option("option", Bytes())})()
        self.assert_equal(cli.option.name_prefix, "--")
        self.assert_(cli.option.matches("--option"))

        cli = make_cli({
            "option": Option("option", Bytes(), name_prefix="++")
        })()
        self.assert_equal(cli.option.name_prefix, "++")
        self.assert_(cli.option.matches("++option"))
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


class CLITestCase(TestCase):
    def test_run(self):
        class TestCLI(CLI):
            foo = Command("foo")
        test_cli = TestCLI()
        with self.assert_raises(CommandMissing):
            test_cli.run([])

        with self.assert_raises(NotImplementedError):
            CLI().run([])


suite = make_suite([ActionTestCase, OptionTestCase, CLITestCase])
