# coding: utf-8
"""
    awwparse.utils
    ~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import os
import math


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
        {key: kwargs.pop(key, value) for key, value in defaults.items()}
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
