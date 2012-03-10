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


class BytesTestCase(TestCase):
    def test_parse(self):
        action = TestAction()
        action.add_option("foo", Option("a", Bytes()))
        self.assert_equal(action.run(["-a", "foo"]), {"foo": "foo"})

        action.add_option("bar", Option("b", Bytes(remaining=True)))
        self.assert_equal(action.run(["-b", "foo", "bar", "baz"]), {
            "bar": ["foo", "bar", "baz"]
        })

        action.add_option("baz", Option("c", Bytes(), Bytes(optional=True)))
        self.assert_equal(action.run(["-c", "foo"]), {"baz": ["foo"]})
        self.assert_equal(
            action.run(["-c", "foo", "bar"]),
            {"baz": ["foo", "bar"]}
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

    def test_parse(self):
        action = TestAction()
        action.add_option("foo", Option("a", String()))
        self.assert_equal(
            action.run(["-a", u"ä".encode("utf-8")]),
            {"foo": u"ä"}
        )

        action.add_option("bar", Option("b", String(remaining=True)))
        self.assert_equal(
            action.run([
                "-b",
                u"ä".encode("utf-8"),
                u"ö".encode("utf-8"),
                u"ü".encode("utf-8")
            ]),
            {"bar": [u"ä", u"ö", u"ü"]}
        )

        action.add_option("baz", Option("c", String(), String(optional=True)))
        self.assert_equal(
            action.run(["-c", u"ä".encode("utf-8")]),
            {"baz": [u"ä"]}
        )
        self.assert_equal(
            action.run(["-c", u"ä".encode("utf-8"), u"ö".encode("utf-8")]),
            {"baz": [u"ä", u"ö"]}
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

    def test_parse(self):
        action = TestAction()
        action.add_option("foo", Option("a", Integer()))
        self.assert_equal(action.run(["-a", "1"]), {"foo": 1})

        action.add_option("bar", Option("b", Integer(remaining=True)))
        self.assert_equal(
            action.run(["-b", "1", "2", "3"]),
            {"bar": [1, 2, 3]}
        )

        action.add_option(
            "baz",
            Option("c", Integer(), Integer(optional=True))
        )
        self.assert_equal(action.run(["-c", "1"]), {"baz": [1]})
        self.assert_equal(action.run(["-c", "1", "2"]), {"baz": [1, 2]})


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
