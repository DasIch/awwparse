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
        namespace = {}
        store(namespace, "foo", "bar")
        self.assert_equal(namespace, {"foo": "bar"})

    def test_append(self):
        namespace = {}
        append(namespace, "foo", "spam")
        append(namespace, "foo", "eggs")
        self.assert_equal(namespace, {"foo": ["spam", "eggs"]})

    def test_add(self):
        namespace = {}
        add(namespace, "foo", "spam")
        add(namespace, "foo", "eggs")
        self.assert_equal(namespace, {"foo": {"spam", "eggs"}})


suite = make_suite([ActionTestCase])
