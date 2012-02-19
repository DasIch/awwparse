# coding: utf-8
"""
    awwparse.testsuite.init
    ~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from awwparse import Namespace
from awwparse.testsuite import make_suite, TestCase


class NamespaceTestCase(TestCase):
    def test_set(self):
        namespace = Namespace()
        namespace.set("key", "value")
        self.assertEqual(namespace["key"], "value")

    def test_delete(self):
        namespace = Namespace({"key": "value"})
        namespace.delete("key")
        self.assertNotIn("key", namespace)


suite = make_suite([NamespaceTestCase])
