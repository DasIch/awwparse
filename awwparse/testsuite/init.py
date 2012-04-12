# coding: utf-8
"""
    awwparse.testsuite.init
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from six import u, StringIO

from awwparse import Option, Command, Arguments, CLI, Integer, String
from awwparse.utils import missing
from awwparse.exceptions import (
    ArgumentMissing, CommandMissing, OptionConflict, CommandConflict,
    UnexpectedArgument, PositionalArgumentMissing, UserTypeError,
    ArgumentConflict
)
from awwparse.testsuite import (
    TestCase, make_suite, py3test, TestCommand, TestCLI
)


class OptionTestCase(TestCase):
    def test_signature(self):
        command = TestCommand(
            options=[("option", Option("-o", String(), String(), String()))]
        )
        for args in [["-o"], ["-o", "foo"], ["-o", "foo", "bar"]]:
            with self.assert_raises(ArgumentMissing):
                command.run(args, passthrough_errors=True)

        command = TestCommand(
            options=[("option", Option("-o", String(), [String(), String()]))]
        )
        self.assert_equal(
            command.run(["-o", "a"]),
            ((), {"option": [u("a")]})
        )
        self.assert_equal(
            command.run(["-o", "a", "b", "c"]),
            ((), {"option": ["a", "b", "c"]})
        )
        for args in [["-o"], ["-o", "a", "b"]]:
            with self.assert_raises(ArgumentMissing):
                command.run(args, passthrough_errors=True)

        command = TestCommand(
            options=[("option", Option("-o", String(), [String(), [String()]]))]
        )
        args = ["-o", "a", "b", "c"]
        for i in range(2, len(args) + 1):
            self.assert_equal(
                command.run(args[:i]),
                ((), {"option": args[1:i] or [missing]})
            )

    def test_get_usage(self):
        option = Option("-a", String(metavar=u("foo")))
        self.assert_equal(option.get_usage(), "-a foo")
        self.assert_equal(option.get_usage(using="long"), u("-a foo"))
        self.assert_equal(option.get_usage(using="both"), u("-a foo"))

        option = Option("-a", "--abc", String(metavar=u("foo")))
        self.assert_equal(option.get_usage(), "-a foo")
        self.assert_equal(option.get_usage(using="long"), u("--abc foo"))
        self.assert_equal(option.get_usage(using="both"), u("-a foo, --abc foo"))

    def test_matches(self):
        option = Option("-o", "--option", String())
        self.assert_equal(option.matches("-a"), (False, "-a"))
        self.assert_equal(option.matches("-o"), (True, ""))
        self.assert_equal(option.matches("--asd"), (False, "--asd"))
        self.assert_equal(option.matches("--option"), (True, ""))

    def test_repr(self):
        self.assert_true(
            repr(Option("-o", String())).startswith("Option('-o'")
        )
        self.assert_true(
            repr(Option("--option", String())).startswith("Option('--option'")
        )
        self.assert_true(
            repr(Option("-o", "--option", String()))
            .startswith("Option('-o', '--option'")
        )
        parts = [repr(String()), "help=None"]
        for part in parts:
            self.assert_in(part, repr(Option("-o", String())))


class CommandTestCase(TestCase):
    def test_from_function(self):
        @Command.from_function(Integer(), Integer())
        def foo(a, b):
            return a + b
        self.assert_equal(foo.run(["1", "1"]), 2)

        @Command.from_function(Integer())
        def bar(*args):
            return sum(args)
        self.assert_equal(bar.run(["1", "1"]), 2)

        @Command.from_function(Integer(), Integer())
        def baz(a=1, b=1):
            return a + b
        self.assert_equal(baz.run([]), 2)
        self.assert_equal(baz.run(["-a", "2", "-b", "2"]), 4)

    @py3test
    def test_from_function_annotations(self):
        """
        @Command.from_function()
        def foo(a: Integer(), b: Integer()):
            return a + b
        self.assert_equal(foo.run(["1", "1"]), 2)

        @Command.from_function()
        def foo(*args: Integer()):
            return sum(args)
        self.assert_equal(foo.run(["1", "1"]), 2)

        @Command.from_function()
        def foo(a: Integer() = 1, b: Integer() = 1):
            return a + b
        self.assert_equal(foo.run([]), 2)
        self.assert_equal(foo.run(["-a", "2", "-b", "2"]), 4)
        """

    def test_from_method(self):
        class Foo(object):
            @Command.from_method(Integer(), Integer())
            def spam(self, a, b):
                return self.add(a, b)

            def add(self, a, b):
                return a + b
        foo = Foo()
        self.assert_equal(foo.spam.run(["1", "1"], default_args=[foo]), 2)

    @py3test
    def test_from_method_annotations(self):
        """
        class Foo(object):
            @Command.from_method()
            def spam(self, a: Integer(), b: Integer()):
                return self.add(a, b)

            def add(self, a, b):
                return a + b
        foo = Foo()
        self.assert_equal(foo.spam.run(["1", "1"], default_args=[foo]), 2)
        """

    @py3test
    def test_main_annotations(self):
        """
        class Foo(Command):
            def main(self, a: Integer(), b: Integer()):
                return a + b
        self.assert_equal(Foo().run(["1", "1"]), 2)
        """

    def test_declarative(self):
        results = []
        class Foo(Command):
            arguments = Integer(metavar="a")

            def main(self, a):
                results.append(a)

        class Bar(Command):
            foo = Foo()

        Bar().run(["foo", "1"])
        self.assert_equal(results, [1])

    def test_option_shorts_and_longs(self):
        command = Command()
        command.add_option("foo", Option("-a", String()))
        command.add_option("bar", Option("--abc", String()))
        self.assert_not_in(None, command.option_shorts)
        self.assert_not_in(None, command.option_longs)

    def test_get_usage(self):
        command = Command()
        command.add_option("foo", Option("-o", String()))
        self.assert_equal(command.get_usage(), u("[-h] [-o foo]"))

        command.add_command("bar", Command())
        self.assert_equal(command.get_usage(), u("[-h] [-o foo] {bar}"))

        command.add_argument(String(metavar="baz"))
        self.assert_equal(command.get_usage(), u("[-h] [-o foo] {bar} baz"))

    def test_add_option(self):
        command = Command()
        a = Option("-a", "--foobar", String())
        command.add_option("foo", a)
        with self.assert_raises(OptionConflict):
            command.add_option("bar", a)
        with self.assert_raises(OptionConflict):
            command.add_option("baz", Option("--foobar", String()))

        command = Command()
        command.add_option("foo", Option("-a", "--asd", String()))
        command.add_option("bar", Option("-b", "--qwe", String()))
        command.add_option(
            "spam",
            Option("-a", "--zxc", String()),
            resolve_conflicts=True
        )
        self.assert_equal(command.option_shorts["-a"].long, "--asd")
        command.add_option(
            "eggs",
            Option("-c", "--zxc", String()),
            resolve_conflicts=True
        )
        self.assert_is(command.option_shorts["-c"].long, None)

        with self.assert_raises(OptionConflict):
            command.add_option(
                "blubb",
                Option("-a", "--asd", String()),
                resolve_conflicts=True
            )
        command.add_option(
            "blubb",
            Option("-a", "--asd", String()),
            resolve_conflicts=True,
            force=True
        )
        command.add_option(
            "bla",
            Option("-a", "--asd", String()),
            force=True
        )

    def test_multiple_options_for_name(self):
        command = TestCommand(
            options=[
                ("foo", Option("-a", Integer())),
                ("foo", Option("-b", Integer()))
            ]
        )
        self.assert_equal(
            command.run(["-a", "1", "-b", "2"]),
            ((), {"foo": 2})
        )

    def test_add_command(self):
        command = Command()
        command.add_command("foobar", Command())
        command.add_command("foobar", Command(), force=True)
        with self.assert_raises(CommandConflict):
            command.add_command("foobar", Command())

    def test_add_argument(self):
        command = Command()
        with self.assert_raises(ValueError):
            command.add_argument(String())
        command.add_argument(String(metavar=u("foo"), remaining=True))
        with self.assert_raises(ArgumentConflict):
            command.add_argument(String(metavar=u("bar")))

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
        command.add_option("foo", Option("-b", String()))
        with self.assert_raises(UnexpectedArgument):
            command.run(["-a"], passthrough_errors=True)

    def test_main(self):
        class TestCommand(Command):
            options = {
                "foo": Option("-a", String()),
                "bar": Option("-b", String())
            }

            def main(self, foo, bar):
                assert foo == u("foo")
                assert bar == u("bar")
        TestCommand().run(["-a", "foo", "-b", "bar"])

    def test_multiple_abbreviations(self):
        command = TestCommand(
            options=[
                ("a", Option("-a", String())),
                ("b", Option("-b", String())),
                ("c", Option("-c", String()))
            ]
        )
        self.assert_equal(
            command.run(["-abc", "foo", "bar", "baz"]),
            ((), {"a": u("foo"), "b": u("bar"), "c": u("baz")})
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
                assert kwargs["foo"] == u("bar")

        class B(Command):
            options = {"foo": Option("-a", String())}
            commands = {"spam": A()}

        B().run(["-a", "bar", "spam"])

    def test_arguments(self):
        class TestCommand(Command):
            arguments = String(metavar=u("foo"))

            def main(self, foo):
                assert foo == u("foo")

        TestCommand().run(["foo"])

        class TestCommand(Command):
            arguments = String(metavar=u("foo")), String(metavar=u("bar"))

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

    def test_nonzero(self):
        self.assert_true(Arguments([1]))
        self.assert_false(Arguments([]))

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


class CLITestCase(TestCase):
    def test_get_usage(self):
        cli = CLI(
            application_name=u("spam"),
            arguments=[String(metavar=u("foo"))]
        )
        self.assert_equal(cli.get_usage(), u("spam [-h] foo"))

        cli.usage = u("blubb")
        self.assert_equal(cli.get_usage(), u("blubb"))

    def test_print_usage(self):
        stringio = StringIO()
        cli = CLI(
            usage=(u("foobarbaz ") * 10).strip(),
            width=40,
            stdout=stringio
        )
        cli.print_usage()
        self.assert_equal(
            stringio.getvalue(), u(
                "Usage: foobarbaz foobarbaz foobarbaz\n"
                "       foobarbaz foobarbaz foobarbaz\n"
                "       foobarbaz foobarbaz foobarbaz\n"
                "       foobarbaz\n"
            )
        )

    def test_print_help(self):
        stringio = StringIO()
        cli = CLI(
            application_name=u("app"),
            stdout=stringio,
            width=40,
            arguments=[String(metavar=u("foo"))]
        )
        cli.print_help()
        self.assert_equal(stringio.getvalue(), u(
            "Usage: app [-h] foo\n"
            "\n"
            "Positional Arguments\n"
            "  foo\n"
            "\n"
            "Options\n"
            "  -h, --help   Show this message\n"
        ))

        cli.stdout = stringio = StringIO()
        cli.add_option("bar", Option("-a", String()))
        cli.print_help()
        self.assert_equal(stringio.getvalue(), u(
            "Usage: app [-h] [-a bar] foo\n"
            "\n"
            "Positional Arguments\n"
            "  foo\n"
            "\n"
            "Options\n"
            "  -h, --help   Show this message\n"
            "  -a bar\n"
        ))

        cli.stdout = stringio = StringIO()
        cli.add_command("baz", Command())
        cli.add_command("spam", Command())
        cli.print_help()
        self.assert_equal(stringio.getvalue() , u(
            "Usage: app [-h] [-a bar] {baz,spam} foo\n"
            "\n"
            "Positional Arguments\n"
            "  foo\n"
            "\n"
            "Options\n"
            "  -h, --help   Show this message\n"
            "  -a bar\n"
            "\n"
            "Commands\n"
            "  baz [-h]\n"
            "  spam [-h]\n"
        ))

    def test_error_handling(self):
        stringio = StringIO()
        def exit(code):
            assert code != 1
        cli = TestCLI(
            application_name=u("app"),
            stdout=stringio,
            stderr=stringio,
            exit=exit,
            width=40,
            options=[("foo", Option("-o", Integer()))]
        )
        with self.assert_raises(AssertionError) as error:
            cli.run(["-o", "foo"])
        self.assert_equal(
            error.exception.args[0], "exit should have aborted execution"
        )
        self.assert_equal(
            stringio.getvalue(),
            u(
                "Error: 'foo' is not an integer\n"
                "Usage: app [-h] [-o foo]\n"
                "\n"
                "Options\n"
                "  -h, --help   Show this message\n"
                "  -o foo\n"
            )
        )
        with self.assert_raises(UserTypeError):
            cli.run(["-o", "foo"], passthrough_errors=True)

        stringio = StringIO()
        cli = TestCLI(
            application_name=u("app"),
            stdout=stringio,
            stderr=stringio,
            exit=exit,
            width=40,
            commands={
                "spam": Command(
                    options=[("foo", Option("-o", String()))]
                )
            }
        )
        with self.assert_raises(AssertionError) as error:
            cli.run(["spam", "-o"])
        self.assert_equal(
            error.exception.args[0],
            "exit should have aborted execution"
        )
        self.assert_equal(
            stringio.getvalue(),
            u(
                "Error: foo\n"
                "Usage: app spam [-h] [-o foo]\n"
                "\n"
                "Options\n"
                "  -h, --help   Show this message\n"
                "  -o foo\n"
            )
        )

    def test_help_option(self):
        stringio = StringIO()
        cli = CLI(application_name=u("app"), stdout=stringio, width=40)
        try:
            cli.run(["-h"])
        except SystemExit:
            pass
        self.assert_equal(
            stringio.getvalue(),
            u(
                "Usage: app [-h]\n"
                "\n"
                "Options\n"
                "  -h, --help   Show this message\n"
            )
        )


suite = make_suite([
    OptionTestCase, CommandTestCase, ArgumentsTestCase, CLITestCase
])
