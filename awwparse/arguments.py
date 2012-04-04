# coding: utf-8
"""
    awwparse.arguments
    ~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import locale
import decimal
from operator import attrgetter
from itertools import takewhile

import six
from six import u
from six.moves import reduce

from awwparse.utils import missing, force_list
from awwparse.exceptions import (
    UserTypeError, ArgumentMissing, EndOptionParsing
)


def parse_argument_signature(arguments, _root=True):
    result = []
    if not _root:
        arguments[0].optional = True
    for argument in arguments:
        if isinstance(argument, Argument):
            result.append(argument)
        else:
            result.extend(parse_argument_signature(argument, _root=False))
    return result


class ContainerArgument(object):
    def __init__(self, *arguments):
        self.arguments = parse_argument_signature(arguments)

    @property
    def default(self):
        if len(self.arguments) == 1:
            return self.arguments[0].default
        return map(
            attrgetter("default"),
            takewhile(
                lambda argument: not argument.optional and argument.default is not missing,
                self.arguments
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
            if isinstance(tree, Argument):
                return tree.usage
            else:
                nodes = u(" ").join(render(node, _root=False) for node in tree)
                if _root:
                    return nodes
                return u("[{0}]").format(nodes)
        return render(reduce(step, self.arguments, ([], ) * 2)[0])

    def setdefault_metavars(self, metavar):
        if isinstance(metavar, six.binary_type):
            metavar = metavar.decode("utf-8")
        for argument in self.arguments:
            if argument.metavar is None:
                argument.metavar = metavar

    def copy(self):
        return self.__class__(
            *[argument.copy() for argument in self.arguments]
        )

    def parse(self, command, arguments):
        result = []
        for argument in self.arguments:
            try:
                result.append(argument.parse(command, arguments))
            except EndOptionParsing:
                break
        return result if len(self.arguments) > 1 else result[0]

    def parse_and_store(self, command, namespace, name, arguments):
        raise NotImplementedError()

    def __repr__(self):
        return "{0}({1})".format(
            self.__class__.__name__,
            ", ".join(map(repr, self.arguments))
        )


class Last(ContainerArgument):
    """
    Stores only the last occurance in the namespace.
    """
    def parse_and_store(self, command, namespace, name, arguments):
        namespace[name] = self.parse(command, arguments)
        return namespace


class List(ContainerArgument):
    """
    Stores every occurance in a list.
    """
    def parse_and_store(self, command, namespace, name, arguments):
        namespace.setdefault(name, []).append(self.parse(command, arguments))
        return namespace


class Set(ContainerArgument):
    """
    Stores every occurance in a set.
    """
    def parse_and_store(self, command, namespace, name, arguments):
        namespace.setdefault(name, set()).add(self.parse(command, arguments))
        return namespace


class Adder(ContainerArgument):
    """
    Stores the sum of every occurance.
    """
    def parse_and_store(self, command, namespace, name, arguments):
        if name in namespace:
            namespace[name] += self.parse(command, arguments)
        else:
            namespace[name] = self.parse(command, arguments)
        return namespace


class Argument(object):
    def __init__(self, metavar=None, default=missing, optional=False,
                 remaining=False, help=None):
        self.metavar = metavar
        self.default = default
        self.optional = optional
        self.remaining = remaining
        self.help = help

    def setdefault_metavar(self, metavar):
        if self.metavar is None:
            self.metavar = metavar

    def copy(self):
        return self.__class__(
            metavar=self.metavar,
            default=self.default,
            optional=self.optional,
            remaining=self.remaining,
            help=self.help
        )

    @property
    def usage(self):
        if self.remaining:
            return u("[{0} ...]").format(self.metavar)
        return self.metavar

    def parse(self, command, arguments):
        raise NotImplementedError()

    def parse_as_positional(self, command, result, arguments):
        parsed = self.parse(command, arguments)
        if self.remaining:
            result.extend(parsed)
        else:
            result.append(parsed)
        return result

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
        return "{0}(metavar={1!r}, default={2!r}, optional={3!r}, remaining={4!r}, help={5!r})".format(
            self.__class__.__name__, self.metavar, self.default, self.optional,
            self.remaining, self.help
        )


class EncodingArgument(Argument):
    error_method = "replace"

    def get_encoding(self, command):
        return getattr(command, "stdin.encoding", locale.getpreferredencoding())


class Bytes(EncodingArgument):
    """
    Represents a binary argument.
    """
    def encode(self, string, encoding):
        if isinstance(string, six.binary_type):
            return string
        try:
            return string.encode(encoding, self.error_method)
        except UnicodeEncodeError:
            raise UserTypeError(
                u("failed to decode {string!r} with {encoding!r}").format(
                    string=string,
                    encoding=encoding
                )
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


class String(EncodingArgument):
    """
    Represents a string argument.
    """
    def decode(self, bytes, encoding):
        if isinstance(bytes, six.text_type):
            return bytes
        try:
            return bytes.decode(encoding, self.error_method)
        except UnicodeDecodeError:
            raise UserTypeError(
                u("failed to decode {bytes!r} with {encoding!r}").format(
                    bytes=bytes,
                    encoding=encoding
                )
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


class NativeString(Argument):
    """
    Represents a "native" string argument.
    """
    def parse(self, command, arguments):
        if self.remaining:
            return list(arguments)
        try:
            return self.get_next_argument(command, arguments)
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise


class ConverterBase(Argument):
    type = None
    type_conversion_exception = ValueError
    error_message = u("")

    def convert(self, argument):
        try:
            return self.type(argument)
        except self.type_conversion_exception:
            raise UserTypeError(self.error_message.format(argument=argument))

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
    """
    Represents an integer argument.
    """
    type = int
    error_message = u("{argument!r} is not an integer")


class Float(ConverterBase):
    """
    Represents a float argument.
    """
    type = float
    error_message = u("{argument!r} is not a float")


class Decimal(ConverterBase):
    """
    Like :class:`Float` but uses :class:`decimal.Decimal` for higher precision.
    """
    type = decimal.Decimal
    type_conversion_exception = decimal.InvalidOperation
    error_message = u("{argument!r} is not a decimal")


class Complex(ConverterBase):
    """
    Represents a complex number argument.
    """
    type = complex
    error_message = u("{argument!r} is not a complex number")


class Any(ConverterBase):
    """
    Represents an argument of one of the given `arguments`.

    Raises a :exc:`UserTypeError` with the given `error_message` if no argument
    successfully parses.
    """
    def __init__(self, arguments, error_message, **kwargs):
        ConverterBase.__init__(self, **kwargs)
        self.arguments = arguments
        self.error_message = error_message

    def copy(self):
        return self.__class__(
            [argument.copy() for argument in self.arguments],
            self.error_message,
            metavar=self.metavar,
            default=self.default,
            optional=self.optional,
            remaining=self.remaining,
            help=self.help
        )

    def convert(self, string):
        for argument in self.arguments:
            try:
                return argument.convert(string)
            except UserTypeError:
                pass
        raise UserTypeError(self.error_message.format(string))

    def __repr__(self):
        return "{0}({1!r}, {2!r}, metavar={3!r}, default={4!r}, optional={5!r}, remaining={6!r}, help={7!r})".format(
            self.__class__.__name__, self.arguments, self.error_message,
            self.metavar, self.default, self.optional, self.remaining,
            self.help
        )


class Number(Any):
    """
    Represents an integer, a float or a complex number.
    """
    def __init__(self, use_decimal=False, **kwargs):
        Any.__init__(
            self,
            [Integer(), (Decimal if use_decimal else Float)(), Complex()],
            u("{argument!r} is not a number"),
            **kwargs
        )
        self.use_decimal = use_decimal

    def copy(self):
        return self.__class__(
            use_decimal=self.use_decimal,
            metavar=self.metavar,
            default=self.default,
            optional=self.optional,
            remaining=self.remaining,
            help=self.help
        )

    def __repr__(self):
        return "{0}(use_decimal={1!r}, metavar={2!r}, default={3!r}, optional={4!r}, remaining={5!r}, help={6!r})".format(
            self.__class__.__name__, self.use_decimal, self.metavar,
            self.default, self.optional, self.remaining, self.help
        )


class Boolean(Argument):
    """
    Represents a boolean.
    """
    def __init__(self, default=False, **kwargs):
        Argument.__init__(self, default=default, **kwargs)

    @property
    def usage(self):
        return u("")

    def parse(self, command, arguments):
        return not self.default


class Choice(Argument):
    """
    Represents a choice between `choices` where the choice is something of
    `argument`.
    """
    def __init__(self, argument, choices, metavar=None, help=None):
        Argument.__init__(self, metavar=metavar, help=None)
        self.argument = argument
        self.choices = choices

    def copy(self):
        return self.__class__(
            self.argument.copy(),
            self.choices,
            metavar=self.metavar,
            help=self.help
        )

    def parse(self, command, arguments):
        parsed = self.argument.parse(command, arguments)
        for choice in force_list(parsed):
            if choice not in self.choices:
                raise UserTypeError(
                    u("{argument!r} not one of {choices}").format(
                        argument=choice,
                        choices=", ".join(map(repr, self.choices))
                    )
                )
        return parsed

    def __repr__(self):
        return "{0}({1!r}, {2!r}, metavar={3!r}, help={4!r})".format(
            self.__class__.__name__, self.argument, self.choices, self.metavar,
            self.help
        )
