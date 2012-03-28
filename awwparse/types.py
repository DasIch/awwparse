# coding: utf-8
"""
    awwparse.types
    ~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import locale
import decimal
from operator import attrgetter
from itertools import takewhile
try:
    reduce
except NameError:
    from functools import reduce

import six

from awwparse.utils import missing, force_list
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


class ContainerType(object):
    def __init__(self, *types):
        self.types = parse_type_signature(types)

    @property
    def default(self):
        if len(self.types) == 1:
            return self.types[0].default
        return map(
            attrgetter("default"),
            takewhile(
                lambda type: not type.optional and type.default is not missing,
                self.types
            )
        ) or missing

    @property
    def usage(self):
        def step(acc, next):
            root, current = acc
            if next.optional:
                current.append([next])
                current = current[-1]
            else:
                current.append(next)
            return root, current

        def render(tree, _root=True):
            if isinstance(tree, Type):
                return tree.usage
            else:
                nodes = " ".join(render(node, _root=False) for node in tree)
                if _root:
                    return nodes
                return "[%s]" % nodes
        return render(reduce(step, self.types, ([], ) * 2)[0])

    def setdefault_metavars(self, metavar):
        for type in self.types:
            if type.metavar is None:
                type.metavar = metavar

    def copy(self):
        return self.__class__(
            *[type.copy() for type in self.types]
        )

    def parse(self, command, arguments):
        result = []
        for type in self.types:
            try:
                result.append(type.parse(command, arguments))
            except EndOptionParsing:
                break
        return result if len(self.types) > 1 else result[0]

    def parse_and_store(self, command, namespace, name, arguments):
        raise NotImplementedError()

    def __repr__(self):
        return "%s(%s)" % (
            self.__class__.__name__,
            ", ".join(map(repr, self.types))
        )


class Last(ContainerType):
    def parse_and_store(self, command, namespace, name, arguments):
        namespace[name] = self.parse(command, arguments)
        return namespace


class List(ContainerType):
    def parse_and_store(self, command, namespace, name, arguments):
        namespace.setdefault(name, []).append(self.parse(command, arguments))
        return namespace


class Set(ContainerType):
    def parse_and_store(self, command, namespace, name, arguments):
        namespace.setdefault(name, set()).add(self.parse(command, arguments))
        return namespace


class Adder(ContainerType):
    def parse_and_store(self, command, namespace, name, arguments):
        if name in namespace:
            namespace[name] += self.parse(command, arguments)
        else:
            namespace[name] = self.parse(command, arguments)
        return namespace


class Type(object):
    def __init__(self, metavar=None, default=missing, optional=False,
                 remaining=False):
        self.metavar = metavar
        self.default = default
        self.optional = optional
        self.remaining = remaining

    def setdefault_metavar(self, metavar):
        if self.metavar is None:
            self.metavar = metavar

    def copy(self):
        return self.__class__(
            metavar=self.metavar,
            default=self.default,
            optional=self.optional,
            remaining=self.remaining
        )

    @property
    def usage(self):
        if self.remaining:
            return "[%s ...]" % self.metavar
        return self.metavar

    def parse(self, command, arguments):
        raise NotImplementedError()

    def get_next_argument(self, command, arguments):
        try:
            argument = next(arguments)
        except StopIteration:
            raise ArgumentMissing(self.metavar)
        else:
            if command.is_option(argument):
                raise ArgumentMissing(argument)
            return argument

    def __repr__(self):
        return "%s(metavar=%r, default=%r, optional=%r, remaining=%r)" % (
            self.__class__.__name__, self.metavar, self.default, self.optional,
            self.remaining
        )


class EncodingType(Type):
    error_method = "replace"

    def get_encoding(self, command):
        return getattr(command, "stdin.encoding", locale.getpreferredencoding())


class Bytes(EncodingType):
    def encode(self, string, encoding):
        if isinstance(string, six.binary_type):
            return string
        try:
            return string.encode(encoding, self.error_method)
        except UnicodeEncodeError:
            raise UserTypeError(
                "failed to decode %r with %r" % (string, encoding)
            )

    def parse(self, command, arguments):
        encoding = self.get_encoding(command)
        if self.remaining:
            return [self.encode(string, encoding) for string in arguments]
        try:
            return self.encode(
                self.get_next_argument(command, arguments),
                encoding
            )
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise


class String(EncodingType):
    def decode(self, bytes, encoding):
        if isinstance(bytes, six.text_type):
            return bytes
        try:
            return bytes.decode(encoding, self.error_method)
        except UnicodeDecodeError:
            raise UserTypeError(
                "failed to decode %r with %r" % (bytes, encoding)
            )

    def parse(self, command, arguments):
        encoding = self.get_encoding(command)
        if self.remaining:
            return [self.decode(bytes, encoding) for bytes in arguments]
        try:
            return self.decode(
                self.get_next_argument(command, arguments),
                encoding
            )
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise


class NativeString(Type):
    def parse(self, command, arguments):
        if self.remaining:
            return list(arguments)
        try:
            return self.get_next_argument(command, arguments)
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

    def parse(self, command, arguments):
        if self.remaining:
            return list(map(self.convert, arguments))
        try:
            argument = self.get_next_argument(command, arguments)
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

    def copy(self):
        return self.__class__(
            [type.copy() for type in self.types],
            self.error_message,
            metavar=self.metavar,
            default=self.default,
            optional=self.optional,
            remaining=self.remaining
        )

    def convert(self, argument):
        for type in self.types:
            try:
                return type.convert(argument)
            except UserTypeError:
                pass
        raise UserTypeError(self.error_message % argument)

    def __repr__(self):
        return "%s(%r, %r, metavar=%r, default=%r, optional=%r, remaining=%r" % (
            self.__class__.__name__, self.types, self.error_message,
            self.metavar, self.default, self.optional, self.remaining
        )


class Number(Any):
    def __init__(self, use_decimal=False, **kwargs):
        Any.__init__(
            self,
            [Integer(), (Decimal if use_decimal else Float)(), Complex()],
            "%r is not a number",
            **kwargs
        )
        self.use_decimal = use_decimal

    def copy(self):
        return self.__class__(
            use_decimal=self.use_decimal,
            metavar=self.metavar,
            default=self.default,
            optional=self.optional,
            remaining=self.remaining
        )

    def __repr__(self):
        return "%s(use_decimal=%r, metavar=%r, default=%r, optional=%r, remaining=%r)" % (
            self.__class__.__name__, self.use_decimal, self.metavar,
            self.default, self.optional, self.remaining
        )


class Boolean(Type):
    def __init__(self, default=False, **kwargs):
        Type.__init__(self, default=default, **kwargs)

    @property
    def usage(self):
        return ""

    def parse(self, command, arguments):
        return not self.default


class Choice(Type):
    def __init__(self, type, choices, metavar=None):
        Type.__init__(self, metavar=metavar)
        self.type = type
        self.choices = choices

    def copy(self):
        return self.__class__(
            self.type.copy(),
            self.choices,
            metavar=self.metavar
        )

    def parse(self, command, arguments):
        parsed = self.type.parse(command, arguments)
        for choice in force_list(parsed):
            if choice not in self.choices:
                raise UserTypeError(
                    "%r not in %s" % (
                        choice,
                        ", ".join(map(repr, self.choices))
                    )
                )
        return parsed

    def __repr__(self):
        return "%s(%r, %r, metavar=%r)" % (
            self.__class__.__name__, self.type, self.choices, self.metavar
        )
