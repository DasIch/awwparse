# coding: utf-8
"""
    awwparse.types
    ~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import locale
import decimal

from awwparse.exceptions import UserTypeError, ArgumentMissing


class Type(object):
    def __init__(self, metavar=None, default=None, optional=False,
                 remaining=False):
        self.metavar = metavar
        self.default = default
        self.optional = optional
        self.remaining = remaining

    def parse(self, action, arguments):
        return NotImplementedError()

    def assert_argument(self, action, argument):
        if action.is_option(argument):
            raise ArgumentMissing(argument)
        return argument

    def get_next_argument(self, action, arguments):
        try:
            argument = arguments.next()
        except StopIteration:
            raise ArgumentMissing()
        else:
            if action.is_option(argument):
                raise ArgumentMissing(argument)
            return argument


class Bytes(Type):
    def parse(self, action, arguments):
        if self.remaining:
            return list(arguments)
        try:
            return self.get_next_argument(action, arguments)
        except (StopIteration, ArgumentMissing):
            if self.optional:
                return self.default
            raise


class String(Type):
    error_method = "replace"

    def get_encoding(self, action):
        return action.stdin.encoding or locale.getpreferredencoding()

    def decode(self, bytes, encoding):
        try:
            return bytes.decode(encoding, self.error_method)
        except UnicodeDecodeError:
            raise UserTypeError(
                "failed to decode %r with %r" % (bytes, encoding)
            )

    def parse(self, action, arguments):
        encoding = self.get_encoding(action)
        if self.remaining:
            return [self.decode(bytes, encoding) for bytes in arguments]
        try:
            return self.decode(
                self.get_next_argument(action, arguments),
                encoding
            )
        except (StopIteration, ArgumentMissing):
            if self.optional:
                return self.default
            raise


class NumberBase(Type):
    type = None
    error_message = ""

    def convert(self, argument):
        try:
            return self.type(argument)
        except ValueError:
            raise UserTypeError(self.error_message % self.argument)

    def parse(self, action, arguments):
        if self.remaining:
            return map(self.convert, arguments)
        try:
            argument = self.get_next_argument(action, arguments)
        except (StopIteration, ArgumentMissing):
            if self.optional:
                return self.default
            raise
        else:
            return self.convert(argument)


class Integer(NumberBase):
    type = int
    error_message = "%r is not an integer"


class Float(NumberBase):
    type = float
    error_message = "%r is not a float"


class Decimal(NumberBase):
    type = decimal.Decimal
    error_message = "%r is not a decimal"


class Complex(NumberBase):
    type = complex
    error_message = "%r is not a complex number"


class Number(NumberBase):
    def __init__(self, metavar=None, use_decimal=False, **kwargs):
        NumberBase.__init__(self, metavar=metavar, **kwargs)
        self.types = [int, decimal.Decimal if use_decimal else float, complex]

    def convert(self, argument):
        for type in self.types:
            try:
                return type(argument)
            except ValueError:
                pass
        raise UserTypeError("%r is not a number" % argument)


class Boolean(Type):
    def __init__(self, metavar=None, default=False, **kwargs):
        Type.__init__(self, metavar=metavar, default=False, **kwargs)

    def parse(self, action, arguments):
        return not self.default


class Choice(Type):
    def __init__(self, type, choices, metavar=None):
        Type.__init__(self, metavar=metavar)
        self.type = type
        self.choices = choices

    def parse(self, action, arguments):
        parsed = self.type(action, arguments)
        for choice in parsed:
            if choice not in self.choices:
                raise UserTypeError(
                    "%r not in %s" % (
                        choice,
                        ", ".join(map(repr, self.choices))
                    )
                )
        return parsed
