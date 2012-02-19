# coding: utf-8
"""
    awwparse.testsuite.utils
    ~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from awwparse.utils import import_string, find_modules
from awwparse.testsuite import TestCase, make_suite


class UtilityTestCase(TestCase):
    def test_import_string(self):
        import cgi
        self.assert_true(import_string("cgi.escape") is cgi.escape)
        self.assert_true(import_string("XXX", silent=True) is None)
        self.assert_true(import_string("cgi.XXX", silent=True) is None)
        with self.assert_raises(ImportError):
            import_string("XXX")
            import_string("cgi.XXX")

    def test_find_modules(self):
        self.assert_equal(list(find_modules("awwparse.testsuite")), [
            "awwparse.testsuite.init",
            "awwparse.testsuite.utils"
        ])


suite = make_suite([UtilityTestCase])
