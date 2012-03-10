# coding: utf-8
"""
    awwparse.testsuite.types
    ~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import decimal
from functools import partial

from awwparse import (
    Bytes, String, Integer, Float, Decimal, Complex, parse_type_signature,
    Option, Type, Any, Number, Choice
)
from awwparse.exceptions import UserTypeError
from awwparse.testsuite import TestCase, make_suite, TestAction


class TypesTestCase(TestCase):
    def test_parse_type_signature(self):
        optionals = partial(map, lambda type: type.optional)

        self.assert_(all(not optional for optional in optionals(
            parse_type_signature((Bytes(), Bytes(), Bytes()))
        )))
        self._assert(all(optionals(
            parse_type_signature(([Bytes(), [Bytes(), [Bytes()]]]))
        )))
        types = parse_type_signature((Bytes(), [Bytes(), Bytes()]))
        self._assert(not types[0].optional)
        self._assert(types[1].optional)
        self._assert(not types[2].optional)

    def test_repr(self):
        self.assert_equal(
            repr(Type()),
            "Type(metavar=None, default=missing, optional=False, remaining=False"
        )


def make_parse_test(type, single, remaining, optional):
    def parse_test(self):
        action = TestAction()
        action.add_option("foo", Option("a", type()))
        for args, expected in single:
            self.assert_equal(
                action.run(["-a"] + args),
                {"foo": expected}
            )

        action.add_option("bar", Option("b", type(remaining=True)))
        for args, expected in remaining:
            self.assert_equal(
                action.run(["-b"] + args),
                {"bar": expected}
            )

        action.add_option("baz", Option("c", type(), type(optional=True)))
        for args, expected in optional:
            self.assert_equal(
                action.run(["-c"] + args),
                {"baz": expected}
            )
    return parse_test


class BytesTestCase(TestCase):
    test_parse = make_parse_test(
        Bytes,
        [(["foo"], "foo")],
        [(["foo", "bar", "baz"], ["foo", "bar", "baz"])],
        [
            (["foo"], ["foo"]),
            (["foo", "bar"], ["foo", "bar"])
        ]
    )


class StringTestCase(TestCase):
    def test_wrong_encoding(self):
        string = String()
        self.assert_equal(
            string.decode(u"ündecödäble".encode("utf-8"), "ascii"),
            u"��ndec��d��ble"
        )

    def test_decode_strict(self):
        class TestString(String):
            error_method = "strict"
        string = TestString()
        with self.assert_raises(UserTypeError):
            string.decode(u"ündecödäble".encode("utf-8"), "ascii")

    test_parse = make_parse_test(
        String,
        [([u"ä".encode("utf-8")], u"ä")],
        [([c.encode("utf-8") for c in u"äöü"], list(u"äöü"))],
        [
            ([u"ä".encode("utf-8")], [u"ä"]),
            ([c.encode("utf-8") for c in u"äö"], [u"ä", u"ö"])
        ]
    )


class AnyTestCase(TestCase):
    def test_repr(self):
        bytes = Bytes()
        self.assert_equal(
            repr(Any([Bytes()], "foo")),
            "Any([%r], 'foo', metavar=None, default=missing, optional=False, remaining=False" % bytes
        )


class IntegerTestCase(TestCase):
    def test_convert(self):
        integer = Integer()
        self.assert_equal(integer.convert("1"), 1)
        with self.assert_raises(UserTypeError):
            integer.convert("1.0")

    test_parse = make_parse_test(
        Integer,
        [(["1"], 1)],
        [(["1", "2", "3"], [1, 2, 3])],
        [
            (["1"], [1]),
            (["1", "2"], [1, 2])
        ]
    )


class FloatingTestCaseMixin(object):
    type = None
    floating_type = None

    def test_convert(self):
        floating = self.type()
        self.assert_equal(floating.convert("1"), self.floating_type("1"))
        self.assert_equal(floating.convert("1.0"), self.floating_type("1.0"))
        with self.assert_raises(UserTypeError):
            floating.convert("1j")


class FloatTestCase(FloatingTestCaseMixin, TestCase):
    type = Float
    floating_type = float


class DecimalTestCase(FloatingTestCaseMixin, TestCase):
    type = Decimal
    floating_type = decimal.Decimal


class ComplexTestCase(TestCase):
    def test_convert(self):
        complex = Complex()
        self.assert_equal(complex.convert("0"), 0j)
        self.assert_equal(complex.convert("0.0"), 0.0j)
        self.assert_equal(complex.convert("1j"), 1j)


class NumberTestCase(TestCase):
    def test_repr(self):
        self.assert_equal(
            repr(Number()),
            "Number(use_decimal=False, metavar=None, default=missing, optional=False, remaining=False)"
        )


class ChoiceTestCase(TestCase):
    def test_repr(self):
        integer = Integer()
        self.assert_equal(
            repr(Choice(integer, [1, 2])),
            "Choice(%r, [1, 2], metavar=None)" % integer
        )


suite = make_suite([
    StringTestCase, IntegerTestCase, FloatTestCase, DecimalTestCase,
    ComplexTestCase, BytesTestCase, AnyTestCase, NumberTestCase, ChoiceTestCase
])
