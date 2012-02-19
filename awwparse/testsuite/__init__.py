# coding: utf-8
"""
    awwparse.testsuite
    ~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import unittest

from awwparse.utils import import_string, find_modules


def make_suite(test_cases):
    """
    Creates a :class:`unittest.TestSuite` from an iterable of
    :class:`unittest.TestCase`\s.
    """
    suite = unittest.TestSuite()
    for test_case in test_cases:
        suite.addTest(unittest.makeSuite(test_case))
    return suite


def iter_suites(package):
    """
    Yields all testsuite.
    """
    # This code has been taken from Werkzeug, see LICENSE.rst for more details
    for import_name in find_modules(package, include_packages=True):
        module = import_string(import_name)
        if hasattr(module, "suite"):
            yield module.suite


def find_all_tests(suite):
    """
    Yields all the tests and their names from a given suite.
    """
    # This code has been taken from Werkzeug, see LICENSE.rst for more details
    suites = [suite]
    while suites:
        suite = suites.pop()
        try:
            suites.extend(suite)
        except TypeError:
            yield suite, "%s.%s.%s" % (
                suite.__class__.__module__,
                suite.__class__.__name__,
                suite._testMethodName
            )


class TestCase(unittest.TestCase):
    """
    Baseclass for all the tests that Awwparse uses. Use these method for
    testing instead of the camelcased ones in the baseclass for consistency.
    """
    # This code has been taken from Werkzeug, see LICENSE.rst for more details

    def setup(self):
        pass

    def teardown(self):
        pass

    def setUp(self):
        self.setup()

    def tearDown(self):
        self.teardown()

    def assert_equal(self, left, right):
        return self.assertEqual(left, right)

    def assert_not_equal(self, left, right):
        return self.assertNotEqual(left, right)

    def assert_raises(self, exc_type, callable=None, *args, **kwargs):
        catcher = _ExceptionCatcher(self, exc_type)
        if callable is None:
            return catcher
        with catcher:
            callable(*args, **kwargs)

    def assert_true(self, x):
        return self.assertTrue(x)


class _ExceptionCatcher(object):
    # This code has been taken from Werkzeug, see LICENSE.rst for more details

    def __init__(self, test_case, exc_type):
        self.test_case = test_case
        self.exc_type = exc_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        exception_name = self.exc_type.__name__
        if exc_type is None:
            self.test_case.fail(
                "Expected exception of type %r" % exception_name
            )
        elif not issubclass(exc_type, self.exc_type):
            raise exc_type, exc_value, traceback
        return True


class BetterLoader(unittest.TestLoader):
    """
    A nicer loader that solves two problems. First of all we are setting up
    tests from different sources and we're doing this programmatically which
    breaks the default loading logic so this is required anyways. Secondly
    this loader has a nicer interpolation for test names than the default one.
    """
    # This code has been taken from Werkzeug, see LICENSE.rst for more details

    def getRootSuite(self):
        return suite()

    def loadTestsFromName(self, name, module=None):
        root = self.getRootSuite()
        if name == "suite":
            return root

        all_tests = []
        for testcase, testname in find_all_tests(root):
            if testname == name or \
               testname.endswith("." + name) or \
               ("." + name + ".") in testname or \
               testname.startswith(name + "."):
                all_tests.append(testcase)

        if not all_tests:
            raise LookupError("could not find test case for \"%s\"" % name)

        if len(all_tests) == 1:
            return all_tests[0]
        result = unittest.TestSuite()
        for test in all_tests:
            result.addTest(test)
        return result


def suite():
    """
    A testsuite that has all the Awwparse tests. You can use this function to
    integrate the Awwparse tests into your own testsuite in case you want to
    test that monkeypatches to Awwparse don't break it.
    """
    # This code has been taken from Werkzeug, see LICENSE.rst for more details
    suite = unittest.TestSuite()
    for other_suite in iter_suites(__name__):
        suite.addTest(other_suite)
    return suite


def main():
    """
    Runs the testsuite as commnd line application.
    """
    # This code has been taken from Werkzeug, see LICENSE.rst for more details
    try:
        unittest.main(testLoader=BetterLoader(), defaultTest="suite")
    except Exception, e:
        print "Error: %s" % e
