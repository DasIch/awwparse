# coding: utf-8
"""
    awwparse.utils
    ~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import os
import math


GOLDEN_RATIO = (1 + math.sqrt(5)) / 2


def set_attributes(object, attributes):
    for name, attribute in attributes.items():
        setattr(object, name, attribute)


def set_attributes_from_kwargs(object, kwargs, defaults):
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


missing = Missing()
del Missing


def force_list(object):
    try:
        return list(object)
    except TypeError:
        return [object]


def get_terminal_width(default_width=80):
    try:
        return int(os.environ["COLUMNS"])
    except (KeyError, ValueError):
        return default_width


def golden_split(n):
    large = n / GOLDEN_RATIO
    small = n - large
    large = int(round(large))
    small = int(round(small))
    return large, small
