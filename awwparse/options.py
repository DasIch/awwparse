# coding: utf-8
"""
    awwparse.options
    ~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from awwparse import Option, mixins


class String(mixins.String, Option):
    pass


class Boolean(mixins.Boolean, Option):
    pass


class Integer(mixins.Integer, Option):
    pass


class Float(mixins.Float, Option):
    pass


class Decimal(mixins.Decimal, Option):
    pass


class Choice(mixins.Choice, Option):
    pass
