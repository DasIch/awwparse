# coding: utf-8
"""
    awwparse.testsuite
    ~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import unittest
from itertools import imap, chain


class TestCase(unittest.TestCase):
    def setup(self):
        pass

    def setUp(self):
        self.setup()

    def teardown(self):
        pass

    def tearDown(self):
        self.teardown()

    def assert_equal(self, *args, **kwargs):
        return self.assertEqual(*args, **kwargs)

    def assert_raises(self, *args, **kwargs):
        return self.assertRaises(*args, **kwargs)


def make_suite(test_cases):
    return unittest.TestSuite(map(unittest.makeSuite, test_cases))


def suite():
    #: .. todo:: Automatically import and add suites from everything below
    #:           :mod:`awwparse.testsuite`.
    from awwparse.testsuite import utils
    return unittest.TestSuite([utils.suite])


def find_all_tests(s):
    if isinstance(s, unittest.TestCase):
        yield s, "%s.%s.%s" % (
            s.__class__.__module__,
            s.__class__.__name__,
            s._testMethodName
        )
    else:
        for grand_child in chain.from_iterable(imap(find_all_tests, s)):
            yield grand_child


class TestLoader(unittest.TestLoader):
    def getRootSuite(self):
        return suite()

    def loadTestsFromName(self, name, module=None):
        root = self.getRootSuite()

        if name == "suite":
            return root

        tests = []
        for test_case, test_name in find_all_tests(root):
            if (test_name == name or
                test_name.endswith(name) or
                ("." + name + ".") in test_name or
                test_name.startswith(name + ".")
                ):
                tests.append(test_case)

        if not tests:
            raise LookupError("could not find a test case matching %r" % name)

        return unittest.TestSuite(tests)


def main():
    unittest.main(testLoader=TestLoader(), defaultTest="suite")
