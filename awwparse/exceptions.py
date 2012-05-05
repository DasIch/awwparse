# coding: utf-8
"""
    awwparse.exceptions
    ~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import os


class CLIError(Exception):
    """
    An exception used in case of a fatal error.
    """
    #: The exit code which should be used in case of failure.
    exit_code = os.EX_USAGE

    @property
    def message(self):
        if self.args:
            return self.args[0]
        return None


class UnexpectedArgument(CLIError):
    pass


class ArgumentMissing(CLIError):
    pass


class UserTypeError(CLIError):
    pass


class CommandMissing(CLIError):
    pass


class PositionalArgumentMissing(CLIError):
    pass


class EndOptionParsing(Exception):
    pass


class Conflict(Exception):
    pass


class OptionConflict(Conflict):
    pass


class CommandConflict(Conflict):
    pass


class PositionalConflict(Conflict):
    pass
