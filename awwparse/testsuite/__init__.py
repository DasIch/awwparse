# coding: utf-8
"""
    awwparse.testsuite
    ~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import re
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import textwrap
from functools import wraps
from itertools import chain

import six
from six.moves import map

from awwparse import Command, CLI


class TestCommand(Command):
    def main(self, *args, **kwargs):
        return args, kwargs


class TestCLI(CLI):
    def main(self, *args, **kwargs):
        return args, kwargs


_begin_word_re = re.compile(r"_([a-z])")
def to_unittest_identifier(identifier):
    return _begin_word_re.sub(lambda m: m.group(1).upper(), identifier)


def is_pep8_identifier(identifier):
    return _begin_word_re.search(identifier) is not None


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
        if is_pep8_identifier(attrname):
            try:
                return getattr(self, to_unittest_identifier(attrname))
            except AttributeError:
                raise AttributeError(attrname)
        raise AttributeError(attrname)


def make_suite(test_cases):
    return unittest.TestSuite(map(unittest.makeSuite, test_cases))


def suite():
    #: .. todo:: Automatically import and add suites from everything below
    #:           :mod:`awwparse.testsuite`.
    from awwparse.testsuite import utils, init, arguments
    return unittest.TestSuite([utils.suite, init.suite, arguments.suite])


def find_all_tests(s):
    if isinstance(s, unittest.TestCase):
        yield s, "{0}.{0}.{0}".format(
            s.__class__.__module__,
            s.__class__.__name__,
            s._testMethodName
        )
    else:
        for grand_child in chain.from_iterable(map(find_all_tests, s)):
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


def py3test(function):
    if six.PY3:
        @wraps(function)
        def new(self):
            code = compile(
                textwrap.dedent(function.__doc__),
                "<{0}>".format(function.__name__),
                "exec"
            )
            six.exec_(code, function.__globals__, locals())
        return new
    else:
        return function


def main():
    unittest.main(testLoader=TestLoader(), defaultTest="suite")
