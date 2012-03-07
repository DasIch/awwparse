# coding: utf-8
"""
    awwparse.testsuite.init
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from awwparse import store, append, add
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


suite = make_suite([ActionTestCase])
