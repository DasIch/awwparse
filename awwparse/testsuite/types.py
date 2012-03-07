# coding: utf-8
"""
    awwparse.testsuite.types
    ~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import decimal

from awwparse import String, Integer, Float, Decimal, Complex
from awwparse.exceptions import UserTypeError
from awwparse.testsuite import TestCase, make_suite


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
