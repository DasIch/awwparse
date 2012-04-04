# coding: utf-8
"""
    awwparse.utils
    ~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from __future__ import absolute_import
import os
import math
import inspect
try:
    from itertools import zip_longest
except ImportError:
    from itertools import izip_longest as zip_longest


#: The golden ratio.
GOLDEN_RATIO = (1 + math.sqrt(5)) / 2


def set_attributes(object, attributes):
    """
    Populates `object` with `attributes` from a mapping.
    """
    for name, attribute in attributes.items():
        setattr(object, name, attribute)


def set_attributes_from_kwargs(object, kwargs, defaults):
    """
    Populates `object` with attributes from `kwargs` as defined by the default
    mapping `defaults`. If an item is contained in `kwargs` that is not defined
    as an attribute by `default` a :exc:`TypeError` is raised.
    """
    set_attributes(
        object,
        dict((key, kwargs.pop(key, value)) for key, value in defaults.items())
    )
    if kwargs:
        raise TypeError(
            "set_attributes_from_kwargs() got an unexpected keyword argument "
            "%r" % kwargs.popitem()[0]
        )


class Missing(object):
    def __nonzero__(self):
        return False

    def __bool__(self):
        return self.__nonzero__()

    def __repr__(self):
        return "missing"


#: Represents a missing value in cases in which ``None`` does not count as
#: such.
missing = Missing()
del Missing


def force_list(object):
    """
    Returns ``list(object)`` or a list containing object.
    """
    try:
        return list(object)
    except TypeError:
        return [object]


def get_terminal_width(default_width=80):
    """
    Returns the width of the terminal.
    """
    try:
        return int(os.environ["COLUMNS"])
    except (KeyError, ValueError):
        return default_width


def golden_split(n):
    """
    Splits the given length `n` into a larger and a smaller part using the
    golden ratio to determine a "perfect" split.
    """
    large = n / GOLDEN_RATIO
    small = n - large
    large = int(round(large))
    small = int(round(small))
    return large, small


try:
    _getargspec = inspect.getfullargspec
    _ArgSpec = inspect.FullArgSpec
except AttributeError:
    _getargspec = inspect.getargspec
    _ArgSpec = inspect.ArgSpec


class Signature(object):
    """
    Represents the signature of a callable object.
    """
    def __init__(self, positional_arguments, keyword_arguments, annotations,
                 arbitary_positional_arguments=None,
                 arbitary_keyword_arguments=None,
                 defaults=None, documentation=None):
        self.positional_arguments = positional_arguments
        self.keyword_arguments = keyword_arguments
        self.annotations = annotations
        self.arbitary_positional_arguments = arbitary_positional_arguments
        self.arbitary_keyword_arguments = arbitary_keyword_arguments
        self.defaults = {} if defaults is None else defaults
        self.documentation = documentation

    @classmethod
    def _from_argspec(cls, argspec, documentation=None):
        defaults = {}
        kwonlydefaults = getattr(argspec, "kwonlydefaults", None)
        if kwonlydefaults is not None:
            defaults.update(kwonlydefaults)
        positional = []
        keyword = []
        for arg, default in zip_longest(reversed(argspec.args),
                                        reversed(argspec.defaults or [])):
            if default is None:
                positional.append(arg)
            else:
                defaults[arg] = default
                keyword.append(arg)
        positional.reverse()
        keyword.reverse()
        keyword.extend(getattr(argspec, "kwonlyargs", []))
        return cls(
            positional,
            keyword,
            getattr(argspec, "annotations", {}),
            argspec.varargs,
            getattr(argspec, "varkw", getattr(argspec, "keywords", None)),
            defaults,
            documentation
        )

    @classmethod
    def from_function(cls, function):
        """
        Returns a :class:`Signature` object for the given `function` or static
        method.
        """
        return cls._from_argspec(
            _getargspec(function), function.__doc__
        )

    @classmethod
    def from_method(cls, method, documentation=None):
        """
        Returns a :class:`Signature` object for the given `method`.
        """
        argspec = _getargspec(method)
        return cls._from_argspec(
            _ArgSpec(
                argspec.args[1:],
                *list(argspec)[1:]
            ),
            method.__doc__ if documentation is None else documentation
        )

    @classmethod
    def from_class(cls, class_):
        """
        Returns a :class:`Signature` object for the given `class_`.
        """
        return cls.from_method(class_.__init__, class_.__doc__)

    @classmethod
    def from_object(cls, object):
        """
        Returns a :class:`Signature` object for the given callable `object`
        implementing :meth:`object.__call__()`.
        """
        return cls.from_method(object.__call__)


def iter_mapping(mapping):
    return mapping.items() if isinstance(mapping, dict) else mapping
