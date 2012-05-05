# coding: utf-8
"""
    awwparse.testsuite.positionals
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import os
import decimal
import json
from functools import partial

try:
    import requests
except ImportError:
    requests = None

import six
from six import BytesIO, StringIO
from six import u

from awwparse import (
    Bytes, String, Integer, Float, Decimal, Complex, Option, Positional, Any,
    Number, Choice, Boolean, NativeString, Mapping, File, Resource
)
from awwparse.positionals import parse_positional_signature
from awwparse.exceptions import UserTypeError
from awwparse.testsuite import (
    TestCase, make_suite, TestCommand, TestCLI, skip_if
)


class ArgumentsTestCase(TestCase):
    def test_parse_positional_signature(self):
        optionals = partial(map, lambda positional: positional.optional)

        self.assert_true(all(not optional for optional in optionals(
            parse_positional_signature((Bytes(), Bytes(), Bytes()))
        )))
        self.assert_true(all(optionals(
            parse_positional_signature([[Bytes(), [Bytes(), [Bytes()]]]])
        )))
        positionals = parse_positional_signature((Bytes(), [Bytes(), Bytes()]))
        self.assert_true(not positionals[0].optional)
        self.assert_true(positionals[1].optional)
        self.assert_true(not positionals[2].optional)


class PositionalTestCase(TestCase):
    def test_repr(self):
        r = repr(Positional())
        parts = [
            "metavar=None", "optional=False", "remaining=False", "help=None"
        ]
        for part in parts:
            self.assert_in(part, r)

def make_parse_test(positional, single, remaining, optional):
    def parse_test(self):
        command = TestCommand()
        command.add_option("foo", Option("-a", positional()))
        for args, expected in single:
            self.assert_equal(
                command.run(["-a"] + args),
                ((), {"foo": expected})
            )

        command.add_option("bar", Option("-b", positional(remaining=True)))
        for args, expected in remaining:
            self.assert_equal(
                command.run(["-b"] + args, passthrough_errors=True),
                ((), {"bar": expected})
            )

        command.add_option(
            "baz",
            Option("-c", positional(), positional(optional=True))
        )
        for args, expected in optional:
            self.assert_equal(
                command.run(["-c"] + args, passthrough_errors=True),
                ((), {"baz": expected})
            )
    return parse_test


class BytesTestCase(TestCase):
    test_parse = make_parse_test(
        Bytes,
        [(["foo"], b"foo")],
        [(["foo", "bar", "baz"], [b"foo", b"bar", b"baz"])],
        [
            (["foo"], [b"foo"]),
            (["foo", "bar"], [b"foo", b"bar"])
        ]
    )


class StringTestCase(TestCase):
    def test_wrong_encoding(self):
        string = String()
        unknown_char = u("\ufffd") * (2 if six.PY3 else 4)
        self.assert_equal(
            string.decode(u("ündecödäble").encode("utf-8"), "ascii"),
            u("%(u)sndec%(u)sd%(u)sble") % {"u": unknown_char}
        )

    def test_decode_strict(self):
        class TestString(String):
            error_method = "strict"
        string = TestString()
        with self.assert_raises(UserTypeError):
            string.decode(u("ündecödäble").encode("utf-8"), "ascii")

    test_parse = make_parse_test(
        String,
        [([u("ä").encode("utf-8")], u("ä"))],
        [([c.encode("utf-8") for c in u("äöü")], list(u("äöü")))],
        [
            ([u("ä").encode("utf-8")], [u("ä")]),
            (
                [u("ä").encode("utf-8"), u("ö").encode("utf-8")],
                [u("ä"), u("ö")]
            )
        ]
    )


class NativeStringTestCase(TestCase):
    test_parse = make_parse_test(
        NativeString,
        [(["foo"], "foo")],
        [(["foo", "bar", "baz"], ["foo", "bar", "baz"])],
        [
            (["foo"], ["foo"]),
            (["foo", "bar"], ["foo", "bar"])
        ]
    )


class AnyTestCase(TestCase):
    def test_parse(self):
        command = TestCommand(
            options=[
                ("foo", Option(
                    "-o",
                    Any([Integer()], u("{argument!r} is not an integer"))
                ))
            ]
        )
        self.assert_equal(command.run(["-o", "1"]), ((), {"foo": 1}))
        with self.assert_raises(UserTypeError):
            command.run(["-o", "foo"])

    def test_repr(self):
        parts = [
            "[{0!r}]".format(Bytes()), "'foo'", "metavar=None",
            "optional=False", "remaining=False", "help=None"
        ]
        for part in parts:
            self.assert_in(part, repr(Any([Bytes()], "foo")))


class IntegerTestCase(TestCase):
    def test_convert(self):
        integer = Integer()
        self.assert_equal(integer.convert("1"), 1)
        with self.assert_raises(UserTypeError):
            integer.convert("1.0")

    test_parse = make_parse_test(
        Integer,
        [([b"1"], 1)],
        [(["1", "2", "3"], [1, 2, 3])],
        [
            (["1"], [1]),
            (["1", "2"], [1, 2])
        ]
    )


class FloatingTestCaseMixin(object):
    argument = None
    floating_type = None

    def test_convert(self):
        floating = self.argument()
        self.assert_equal(floating.convert("1"), self.floating_type("1"))
        self.assert_equal(floating.convert("1.0"), self.floating_type("1.0"))
        with self.assert_raises(UserTypeError):
            floating.convert("1j")


class FloatTestCase(FloatingTestCaseMixin, TestCase):
    argument = Float
    floating_type = float

    test_parse = make_parse_test(
        Float,
        [(["1.0"], 1.0)],
        [(["1.0", "2.0", "3.0"], [1.0, 2.0, 3.0])],
        [
            (["1.0"], [1.0]),
            (["1.0", "2.0"], [1.0, 2.0])
        ]
    )


class DecimalTestCase(FloatingTestCaseMixin, TestCase):
    argument = Decimal
    floating_type = decimal.Decimal

    test_parse = make_parse_test(
        Decimal,
        [(["1.0"], decimal.Decimal("1.0"))],
        [(
            ["1.0", "2.0", "3.0"],
            [decimal.Decimal("1.0"), decimal.Decimal("2.0"), decimal.Decimal("3.0")]
        )],
        [
            (["1.0"], [decimal.Decimal("1.0")]),
            (["1.0", "2.0"], [decimal.Decimal("1.0"), decimal.Decimal("2.0")])
        ]
    )


class ComplexTestCase(TestCase):
    def test_convert(self):
        complex = Complex()
        self.assert_equal(complex.convert("0"), 0j)
        self.assert_equal(complex.convert("0.0"), 0.0j)
        self.assert_equal(complex.convert("1j"), 1j)

    test_parse = make_parse_test(
        Complex,
        [(["1j"], 1j)],
        [(["1j", "2j", "3j"], [1j, 2j, 3j])],
        [
            (["1j"], [1j]),
            (["1j", "2j"], [1j, 2j])
        ]
    )


class NumberTestCase(TestCase):
    def test_repr(self):
        parts = [
            "use_decimal=False", "metavar=None", "optional=False",
            "remaining=False", "help=None"
        ]
        for part in parts:
            self.assert_in(part, repr(Number()))

    test_parse = make_parse_test(
        Number,
        [
            (["1"], 1),
            (["1.0"], 1.0),
            (["1j"], 1j)
        ],
        [(["1", "1.0", "1j"], [1, 1.0, 1.j])],
        [
            (["1"], [1]),
            (["1", "1.0"], [1, 1.0])
        ]
    )


class BooleanTestCase(TestCase):
    def test_parse(self):
        command = TestCommand()
        command.add_option("foo", Option("-a", Boolean()))
        self.assert_equal(
            command.run(["-a"]),
            ((), {"foo": True})
        )

        command.add_option("bar", Option("-b", Boolean(store=False)))
        self.assert_equal(
            command.run(["-b"]),
            ((), {"bar": False})
        )



class ChoiceTestCase(TestCase):
    def test_repr(self):
        integer = Integer()
        r = repr(Choice(integer, [1, 2]))
        parts = [
            repr(integer), "[1, 2]", "metavar=None", "help=None",
            "optional=False", "remaining=False"
        ]
        for part in parts:
            self.assert_in(part, r)

    def test_parse(self):
        action = TestCommand(
            options=[("foo", Option("-a", Choice(Integer(), [1, 2])))]
        )
        self.assert_equal(
            action.run(["-a", "1"]),
            ((), {"foo": 1})
        )
        self.assert_equal(
            action.run(["-a", "2"]),
            ((), {"foo": 2})
        )
        with self.assert_raises(UserTypeError):
            action.run(["-a", "3"], passthrough_errors=True)


class MappingTestCase(TestCase):
    def test_parse(self):
        command = TestCommand(
            options=[
                ("foo", Option("-o", Mapping(NativeString(), {"spam": 1})))
            ]
        )
        with self.assert_raises(UserTypeError):
            command.run(["-o", "eggs"])
        self.assert_equal(command.run(["-o", "spam"]), ((), {"foo": 1}))

        command = TestCommand(
            options=[
                ("foo", Option("-o", Mapping(
                    NativeString(), {"spam": 1}, remaining=True
                )))
            ]
        )
        self.assert_equal(
            command.run(["-o", "spam", "spam"]),
            ((), {"foo": [1, 1]})
        )


class FileTestCase(TestCase):
    def test_parse(self):
        stdin = StringIO("foobar")
        cli = TestCLI(options=[("foo", Option("-o", File()))], stdin=stdin)
        opener = cli.run(["-o", "-"])[1]["foo"]
        with opener as file:
            self.assert_equal(file.read(), "foobar")

        stdout = BytesIO()
        cli = TestCLI(
            options=[
                ("foo", Option("-o", File(mode="w")))
            ],
            stdout=stdout
        )
        opener = cli.run(["-o", "-"])[1]["foo"]
        with opener as file:
            file.write(b"foobar")
        self.assert_equal(stdout.getvalue(), b"foobar")

        stdout = BytesIO()
        cli = TestCLI(
            options=[
                ("foo", Option("-o", File(mode="w", encoding="utf-8")))
            ],
            stdout=stdout
        )
        opener = cli.run(["-o", "-"])[1]["foo"]
        with opener as file:
            file.write(u("äöü"))
        self.assert_equal(stdout.getvalue(), u("äöü").encode("utf-8"))

        with self.assert_raises(ValueError):
            File(mode="r+")
        File(mode="r+", allow_std_streams=False)

        try:
            cli = TestCLI(
                options=[
                    ("foo", Option(
                        "-o", File(mode="wb", allow_std_streams=False))
                    )
                ]
            )
            opener = cli.run(["-o", "FileTestCase.test_parse.txt"])[1]["foo"]
            with opener as file:
                file.write(b"foobar")

            cli = TestCLI(
                options=[
                    ("foo", Option(
                        "-o", File(mode="rb", allow_std_streams=False))
                    )
                ]
            )
            opener = cli.run(["-o", "FileTestCase.test_parse.txt"])[1]["foo"]
            with opener as file:
                self.assert_equal(file.read(), b"foobar")
        finally:
            os.remove("FileTestCase.test_parse.txt")


    def test_repr(self):
        parts = [
            "mode='r'", "buffering=-1", "encoding=None", "errors=None",
            "newline=None", "opener=None", "std_stream_argument='-'",
            "allow_std_streams=True", "close_std_stream=False"
        ]
        for part in parts:
            self.assert_in(part, repr(File()))


class ResourceTestCase(TestCase):
    def test_parse_file(self):
        cli = TestCLI(options=[("foo", Option("-o", Resource()))])
        try:
            test_name = "ResourceTestCase.test_parse_local.txt"
            with open(test_name, "wb") as f:
                f.write(b"foobar")
            opener = cli.run(["-o", "file://" + test_name])[1]["foo"]
            with opener as f:
                self.assert_equal(f.read(), "foobar")
        finally:
            os.remove(test_name)

    @skip_if(requests is None, "requires requests")
    def test_parse_http(self):
        cli = TestCLI(options=[("foo", Option("-o", Resource()))])
        opener = cli.run(["-o", "http://httpbin.org/user-agent"])[1]["foo"]
        with opener as response:
            self.assert_equal(
                json.loads(response.content),
                {u("user-agent"): u("Awwparse/0.1-dev")}
            )

    @skip_if(requests is not None, "requires requests not to be installed")
    def test_parse_http_fails(self):
        cli = TestCLI(options=[("foo", Option("-o", Resource()))])
        with self.assert_raises(RuntimeError):
            cli.run(["-o", "http://httpbin.org"])


suite = make_suite([
    StringTestCase, IntegerTestCase, FloatTestCase, DecimalTestCase,
    ComplexTestCase, BytesTestCase, AnyTestCase, NumberTestCase,
    ChoiceTestCase, BooleanTestCase, PositionalTestCase, ArgumentsTestCase,
    NativeStringTestCase, MappingTestCase, FileTestCase, ResourceTestCase
])
