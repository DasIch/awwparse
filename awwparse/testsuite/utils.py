# coding: utf-8
"""
    awwparse.testsuite.utils
    ~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from awwparse.utils import (
    set_attributes, set_attributes_from_kwargs, missing, force_list,
    get_terminal_width, Signature, OrderedDict, iter_mapping, create_repr,
    ensure_all
)
from awwparse.testsuite import TestCase, make_suite, py3test


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
        self.assert_true(not missing)
        self.assert_equal(repr(missing), "missing")

    def test_force_list(self):
        self.assert_equal(force_list(1), [1])
        self.assert_equal(force_list("abc"), ["a", "b", "c"])

    def test_get_terminal_width(self):
        # check that it doesn't raise an exception and returns an integer
        self.assert_is_instance(get_terminal_width(), int)

    def test_iter_mapping(self):
        self.assert_equal(
            list(iter_mapping([("foo", 1), ("bar", 2)])),
            [("foo", 1), ("bar", 2)]
        )
        self.assert_equal(
            list(iter_mapping({"foo": 1, "bar": 2})),
            [("foo", 1), ("bar", 2)]
        )

    def test_create_repr(self):
        self.assert_equal(create_repr("foo"), "foo()")
        self.assert_equal(
            create_repr("foo", ["bar", "baz"]),
            "foo('bar', 'baz')"
        )
        self.assert_equal(
            create_repr("foo", kwargs={"spam": "eggs"}),
            "foo(spam='eggs')"
        )
        self.assert_equal(
            create_repr("foo", ["bar", "baz"], {"spam": "eggs"}),
            "foo('bar', 'baz', spam='eggs')"
        )

    def test_ensure_names(self):
        with self.assert_raises(AssertionError):
            ensure_all(["name_that_does_not_exist"])
        ensure_all(["AssertionError"])


class SignatureTestCase(TestCase):
    def test_from_function(self):
        function = lambda: None
        signature = Signature.from_function(function)
        self.assert_equal(signature.positional_arguments, [])
        self.assert_equal(signature.keyword_arguments, [])
        self.assert_equal(signature.annotations, {})
        self.assert_equal(signature.arbitary_positional_arguments, None)
        self.assert_equal(signature.arbitary_keyword_arguments, None)
        self.assert_equal(signature.defaults, {})
        self.assert_equal(signature.documentation, None)

        function = lambda a, b: None
        signature = Signature.from_function(function)
        self.assert_equal(signature.positional_arguments, ["a", "b"])

        function = lambda a=1, b=2: None
        signature = Signature.from_function(function)
        self.assert_equal(signature.positional_arguments, ["a", "b"])
        self.assert_equal(signature.keyword_arguments, [])
        self.assert_equal(signature.defaults, {"a": 1, "b": 2})

        def function():
            """Test"""
        signature = Signature.from_function(function)
        self.assert_equal(signature.documentation, "Test")

    @py3test
    def test_from_function_with_keyword_only_arguments(self):
        """
        function = lambda a=1, *args, b=2: None
        signature = Signature.from_function(function)
        self.assert_equal(signature.positional_arguments, ["a"])
        self.assert_equal(signature.keyword_arguments, ["b"])
        self.assert_equal(signature.defaults, {"a": 1, "b": 2})
        """

    @py3test
    def test_from_function_with_annotations(self):
        """
        def function(a: int, b: int):
            pass
        signature = Signature.from_function(function)
        self.assert_equal(signature.annotations, {"a": int, "b": int})
        """

    def test_from_method(self):
        class TestClass(object):
            def test_method(self, a, b):
                """Test"""
        signature = Signature.from_method(TestClass.test_method)
        self.assert_equal(signature.positional_arguments, ["a", "b"])
        self.assert_equal(signature.documentation, "Test")

        signature = Signature.from_method(
            TestClass.test_method,
            documentation="Foo"
        )
        self.assert_equal(signature.documentation, "Foo")

        signature = Signature.from_method(TestClass().test_method)
        self.assert_equal(signature.positional_arguments, ["a", "b"])

    def test_from_class(self):
        class TestClass(object):
            def __init__(self, a, b):
                pass
        signature = Signature.from_class(TestClass)
        self.assert_equal(signature.positional_arguments, ["a", "b"])

    def test_from_object(self):
        class TestClass(object):
            def __call__(self, a, b):
                pass
        signature = Signature.from_object(TestClass())
        self.assert_equal(signature.positional_arguments, ["a", "b"])

    def test_names(self):
        def function(a, b, c=None, *args, **kwargs):
            pass
        self.assert_equal(
            Signature.from_function(function).names,
            ["a", "b", "c", "args", "kwargs"]
        )


class OrderedDictTestCase(TestCase):
    def test_popitem(self):
        d = OrderedDict([("foo", 1), ("bar", 2), ("baz", 3)])
        self.assert_equal(d.popitem(), ("baz", 3))
        self.assert_equal(d, OrderedDict([("foo", 1), ("bar", 2)]))
        self.assert_equal(d.popitem(last=False), ("foo", 1))
        self.assert_equal(d, OrderedDict([("bar", 2)]))

    def test_move_to_end(self):
        d = OrderedDict([("foo", 1), ("bar", 2), ("baz", 3)])
        d.move_to_end("foo")
        self.assert_equal(d, OrderedDict([("bar", 2), ("baz", 3), ("foo", 1)]))
        d.move_to_end("foo", last=False)
        self.assert_equal(d, OrderedDict([("foo", 1), ("bar", 2), ("baz", 3)]))


suite = make_suite([UtilsTestCase, SignatureTestCase, OrderedDictTestCase])
