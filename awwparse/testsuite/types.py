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
    Action, Option
)
from awwparse.exceptions import UserTypeError
from awwparse.testsuite import TestCase, make_suite


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


class BytesTestCase(TestCase):
    def test_parse(self):
        action = Action()
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


class IntegerTestCase(TestCase):
    def test_convert(self):
        integer = Integer()
        self.assert_equal(integer.convert("1"), 1)
        with self.assert_raises(UserTypeError):
            integer.convert("1.0")


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


suite = make_suite([
    StringTestCase, IntegerTestCase, FloatTestCase, DecimalTestCase,
    ComplexTestCase
])
