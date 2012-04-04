# coding: utf-8
"""
    awwparse.testsuite.arguments
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import decimal
from functools import partial

import six
from six import u

from awwparse import (
    Bytes, String, Integer, Float, Decimal, Complex, Option, Argument, Any, Number,
    Choice, Boolean, Last, List, Set, Adder, ContainerArgument, NativeString
)
from awwparse.arguments import parse_argument_signature
from awwparse.exceptions import UserTypeError
from awwparse.testsuite import TestCase, make_suite, TestCommand


class ArgumentsTestCase(TestCase):
    def test_parse_argument_signature(self):
        optionals = partial(map, lambda argument: argument.optional)

        self.assert_true(all(not optional for optional in optionals(
            parse_argument_signature((Bytes(), Bytes(), Bytes()))
        )))
        arguments = parse_argument_signature([[Bytes(), [Bytes(), [Bytes()]]]])
        self.assert_true(all(optionals(
            parse_argument_signature([[Bytes(), [Bytes(), [Bytes()]]]])
        )))
        arguments = parse_argument_signature((Bytes(), [Bytes(), Bytes()]))
        self.assert_true(not arguments[0].optional)
        self.assert_true(arguments[1].optional)
        self.assert_true(not arguments[2].optional)


class ArgumentTestCase(TestCase):
    def test_usage(self):
        container = ContainerArgument(Bytes(metavar=u("foo")))
        self.assert_equal(container.usage, u("foo"))

        container = ContainerArgument(Bytes(metavar=u("foo"), optional=True))
        self.assert_equal(container.usage, u("[foo]"))

        container = ContainerArgument(
            Bytes(metavar=u("foo")),
            Bytes(metavar=u("bar"), optional=True)
        )
        self.assert_equal(container.usage, u("foo [bar]"))

        container = ContainerArgument(
            Bytes(metavar=("foo")),
            Bytes(metavar=("bar"), optional=True),
            Bytes(metavar=("baz"))
        )
        self.assert_equal(container.usage, u("foo [bar baz]"))

        container = ContainerArgument(Bytes(metavar=u("foo"), remaining=True))
        self.assert_equal(container.usage, u("[foo ...]"))

    def test_repr(self):
        self.assert_equal(
            repr(Argument()),
            "Argument(metavar=None, default=missing, optional=False, remaining=False, help=None)"
        )


class LastTestCase(TestCase):
    def test_parse_and_store(self):
        command = TestCommand()
        command.add_option("foo", Option("a", Last(String())))
        self.assert_equal(
            command.run(["-a", "foo", "-a", "bar"]),
            {"foo": u("bar")}
        )


class ListTestCase(TestCase):
    def test_parse_and_store(self):
        command = TestCommand()
        command.add_option("foo", Option("a", List(String())))
        self.assert_equal(
            command.run(["-a", "foo", "-a", "bar"]),
            {"foo": [u("foo"), u("bar")]}
        )


class SetTestCase(TestCase):
    def test_parse_and_store(self):
        command = TestCommand()
        command.add_option("foo", Option("a", Set(String())))
        self.assert_equal(
            command.run(["-a", "foo", "-a", "bar"]),
            {"foo": set([u("foo"), u("bar")])}
        )


class AdderTestCase(TestCase):
    def test_parse_and_store(self):
        command = TestCommand()
        command.add_option("foo", Option("a", Adder(Integer())))
        self.assert_equal(
            command.run(["-a", "1", "-a", "1"]),
            {"foo": 2}
        )


def make_parse_test(argument, single, remaining, optional):
    def parse_test(self):
        command = TestCommand()
        command.add_option("foo", Option("a", argument()))
        for args, expected in single:
            self.assert_equal(
                command.run(["-a"] + args),
                {"foo": expected}
            )

        command.add_option("bar", Option("b", argument(remaining=True)))
        for args, expected in remaining:
            self.assert_equal(
                command.run(["-b"] + args, passthrough_errors=True),
                {"bar": expected}
            )

        command.add_option("baz", Option("c", argument(), argument(optional=True)))
        for args, expected in optional:
            self.assert_equal(
                command.run(["-c"] + args, passthrough_errors=True),
                {"baz": expected}
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
    def test_repr(self):
        bytes = Bytes()
        self.assert_equal(
            repr(Any([Bytes()], "foo")),
            "Any([%r], 'foo', metavar=None, default=missing, optional=False, remaining=False, help=None)" % bytes
        )


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
        self.assert_equal(
            repr(Number()),
            "Number(use_decimal=False, metavar=None, default=missing, optional=False, remaining=False, help=None)"
        )

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
        command.add_option("foo", Option("a", Boolean()))
        self.assert_equal(command.run([]), {"foo": False})
        self.assert_equal(command.run(["-a"]), {"foo": True})

        command.add_option("bar", Option("b", Boolean(default=True)))
        self.assert_equal(command.run([]), {"foo": False, "bar": True})
        self.assert_equal(command.run(["-b"]), {"foo": False, "bar": False})



class ChoiceTestCase(TestCase):
    def test_repr(self):
        integer = Integer()
        self.assert_equal(
            repr(Choice(integer, [1, 2])),
            "Choice(%r, [1, 2], metavar=None, help=None)" % integer
        )

    def test_parse(self):
        action = TestCommand()
        action.add_option("foo", Option("a", Choice(Integer(), [1, 2])))
        self.assert_equal(action.run(["-a", "1"]), {"foo": 1})
        self.assert_equal(action.run(["-a", "2"]), {"foo": 2})
        with self.assert_raises(UserTypeError):
            action.run(["-a", "3"], passthrough_errors=True)


suite = make_suite([
    StringTestCase, IntegerTestCase, FloatTestCase, DecimalTestCase,
    ComplexTestCase, BytesTestCase, AnyTestCase, NumberTestCase,
    ChoiceTestCase, BooleanTestCase, ArgumentTestCase, ArgumentsTestCase,
    LastTestCase, ListTestCase, SetTestCase, AdderTestCase,
    NativeStringTestCase
])
