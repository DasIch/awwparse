# coding: utf-8
"""
    awwparse.arguments
    ~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from awwparse import Argument, mixins


class String(mixins.String, Argument):
    pass


class Integer(mixins.Integer, Argument):
    pass


class Float(mixins.Float, Argument):
    pass


class Decimal(mixins.Decimal, Argument):
    pass


class Choice(mixins.Choice, Argument):
    pass
