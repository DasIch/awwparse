# coding: utf-8
"""
    awwparse.mixins
    ~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from decimal import Decimal

from awwparse import BooleanAction


class ValidationError(ValueError):
    pass


class String(object):
    def validate(self, value):
        return value


class Boolean(object):
    action_type = BooleanAction
    nargs = 0
    default = False

    def action(self, namespace, name):
        namespace.set(name, not self.default)

    def validate(self, value):
        return value


class Simple(object):
    convert = None
    validation_error_msg = ""

    def validate(self, value):
        try:
            return self.convert(value)
        except ValueError:
            raise ValidationError(self.validation_error_msg % value)


class Integer(Simple):
    convert = int
    default = 0
    validation_error_msg = "%r does not match [+-]?[0-9]+"


class Floating(Simple):
    validation_error_msg = "%r does not match [+-]?([0-9]+(\\.[0-9]*)?|\\.[0-9]+)([eE][+-]?[0-9]+)?"


class Float(Floating):
    convert = float


class Decimal(Floating):
    convert = Decimal


class Choice(object):
    def __init__(self, choices, *args, **kwargs):
        super(Choice, self).__init__(*args, **kwargs)
        self.choices = choices

    def validate(self, value):
        if value in self.choices:
            return self.choices[value]
        raise ValidationError(
            "%r is not a valid choice, choose one of %s" % (
                value, ", ".join(self.choices)
            )
        )
