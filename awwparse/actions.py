# coding: utf-8
"""
    awwparse.actions
    ~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""


def store_value(value):
    def store(namespace, name, _=None):
        namespace.set(name, value)
    return store
