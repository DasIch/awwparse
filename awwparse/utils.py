# coding: utf-8
"""
    awwparse.utils
    ~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""


def set_attributes(object, attributes):
    for name, attribute in attributes.iteritems():
        setattr(object, name, attribute)


def set_attributes_from_kwargs(object, kwargs, defaults):
    set_attributes(
        object,
        {key: kwargs.pop(key, value) for key, value in defaults.iteritems()}
    )
    if kwargs:
        raise TypeError(
            "set_attributes_from_kwargs() got an unexpected keyword argument "
            "%r" % kwargs.popitem()[0]
        )


class Missing(object):
    def __nonzero__(self):
        return False

    def __repr__(self):
        return "missing"


missing = Missing()
del Missing
