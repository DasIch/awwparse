# coding: utf-8
"""
    awwparse.exceptions
    ~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""


class CLIError(Exception):
    """
    An exception used internally in case of a fatal error.
    """


class UnexpectedOption(CLIError):
    pass


class UnexpectedArgument(CLIError):
    pass


class ArgumentMissing(CLIError):
    pass


class UserTypeError(CLIError):
    pass


class CommandMissing(CLIError):
    pass


class EndOptionParsing(Exception):
    pass


class OptionConflict(Exception):
    pass


class CommandConflict(Exception):
    pass
