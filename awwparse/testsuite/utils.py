# coding: utf-8
"""
    awwparse.testsuite.utils
    ~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from awwparse.utils import (
    set_attributes, set_attributes_from_kwargs, missing, force_list
)
from awwparse.testsuite import TestCase, make_suite


class TestObject(object):
    pass


class UtilsTestCase(TestCase):
    def test_set_attributes(self):
        object = TestObject()
        set_attributes(object, {
            "foo": "spam",
            "bar": "eggs"
        })
        self.assert_equal(object.foo, "spam")
        self.assert_equal(object.bar, "eggs")

    def test_set_attributes_from_kwargs(self):
        defaults = {"foo": 1, "bar": 2}

        object = TestObject()
        set_attributes_from_kwargs(object, {}, defaults)
        self.assert_equal(object.foo, 1)
        self.assert_equal(object.bar, 2)

        object = TestObject()
        with self.assert_raises(TypeError):
            set_attributes_from_kwargs(object, {"baz": 3}, defaults)

        object = TestObject()
        set_attributes_from_kwargs(object, {"foo": 3, "bar": 4}, defaults)
        self.assert_equal(object.foo, 3)
        self.assert_equal(object.bar, 4)

    def test_missing(self):
        self.assert_(not missing)
        self.assert_equal(repr(missing), "missing")

    def test_force_list(self):
        self.assert_equal(force_list(1), [1])
        self.assert_equal(force_list("abc"), ["a", "b", "c"])


suite = make_suite([UtilsTestCase])
