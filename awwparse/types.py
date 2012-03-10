# coding: utf-8
"""
    awwparse.types
    ~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import locale
import decimal

from awwparse.utils import missing
from awwparse.exceptions import (
    UserTypeError, ArgumentMissing, EndOptionParsing
)


def parse_type_signature(types, _root=True):
    result = []
    if not _root:
        types[0].optional = True
    for type in types:
        if isinstance(type, Type):
            result.append(type)
        else:
            result.extend(parse_type_signature(type, _root=False))
    return result


class Type(object):
    def __init__(self, metavar=None, default=missing, optional=False,
                 remaining=False):
        self.metavar = metavar
        self.default = default
        self.optional = optional
        self.remaining = remaining

    def parse(self, action, arguments):
        return NotImplementedError()

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
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise


class String(Type):
    error_method = "replace"

    def get_encoding(self, action):
        return getattr(action, "stdin.encoding", locale.getpreferredencoding())
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
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise


class ConverterBase(Type):
    type = None
    type_conversion_exception = ValueError
    error_message = ""

    def convert(self, argument):
        try:
            return self.type(argument)
        except self.type_conversion_exception:
            raise UserTypeError(self.error_message % argument)

    def parse(self, action, arguments):
        if self.remaining:
            return map(self.convert, arguments)
        try:
            argument = self.get_next_argument(action, arguments)
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise
        else:
            return self.convert(argument)


class Integer(ConverterBase):
    type = int
    error_message = "%r is not an integer"


class Float(ConverterBase):
    type = float
    error_message = "%r is not a float"


class Decimal(ConverterBase):
    type = decimal.Decimal
    type_conversion_exception = decimal.InvalidOperation
    error_message = "%r is not a decimal"


class Complex(ConverterBase):
    type = complex
    error_message = "%r is not a complex number"


class Any(ConverterBase):
    def __init__(self, types, error_message, **kwargs):
        ConverterBase.__init__(self, **kwargs)
        self.types = types
        self.error_message = error_message

    def convert(self, argument):
        for type in self.types:
            try:
                return type.convert(argument)
            except UserTypeError:
                pass
        raise UserTypeError(self.error_message % argument)


class Number(Any):
    def __init__(self, use_decimal=False, **kwargs):
        Any.__init__(
            [Integer, Decimal if use_decimal else Float, Complex],
            "%r is not a number",
            **kwargs
        )


class Boolean(Type):
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
