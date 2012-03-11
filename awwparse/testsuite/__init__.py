# coding: utf-8
"""
    awwparse.testsuite
    ~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import unittest
import re
from itertools import imap, chain

from awwparse import Command


class TestCommand(Command):
    def main(self, **kwargs):
        return kwargs


_begin_word_re = re.compile(r"_([a-z])")
def to_unittest_identifier(identifier):
    return _begin_word_re.sub(lambda m: m.group(1).upper(), identifier)


class TestCase(unittest.TestCase):
    def setup(self):
        pass

    def setUp(self):
        self.setup()

    def teardown(self):
        pass

    def tearDown(self):
        self.teardown()

    def __getattr__(self, attrname):
        try:
            return getattr(self, to_unittest_identifier(attrname))
        except AttributeError:
            raise AttributeError(attrname)


def make_suite(test_cases):
    return unittest.TestSuite(map(unittest.makeSuite, test_cases))


def suite():
    #: .. todo:: Automatically import and add suites from everything below
    #:           :mod:`awwparse.testsuite`.
    from awwparse.testsuite import utils, init, types
    return unittest.TestSuite([utils.suite, init.suite, types.suite])


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
