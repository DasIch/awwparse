# coding: utf-8
"""
    awwparse.testsuite.actions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from awwparse import store_last, append_to_list, add_to_set, add, sub
from awwparse.testsuite import TestCase, make_suite


class ActionsTestCase(TestCase):
    def test_store_last(self):
        self.assert_equal(store_last(1, 2), 2)

    def test_append_to_list(self):
        self.assert_equal(append_to_list(None, 1), [1])
        self.assert_equal(append_to_list([1], 2), [1, 2])

    def test_add_to_set(self):
        self.assert_equal(add_to_set(None, 1), set([1]))
        self.assert_equal(add_to_set(set([1]), 2), set([1, 2]))

    def test_add(self):
        self.assert_equal(add(None, 1), 1)
        self.assert_equal(add(1, 1), 2)

    def test_sub(self):
        self.assert_equal(sub(None, 1), -1)
        self.assert_equal(sub(1, 1), 0)


suite = make_suite([ActionsTestCase])
