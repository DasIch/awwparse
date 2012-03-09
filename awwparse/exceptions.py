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
    def __init__(self, name, abbreviation=None):
        if abbreviation is None:
            message = "%(name)s is unexpected"
        else:
            message = "%(abbreviation)s in %(name) is unexpected"
        CLIError.__init__(self, message % {
            "name": name,
            "abbreviation": abbreviation
        })
        self.name = name
        self.abbreviation = abbreviation


class UnexpectedArgument(CLIError):
    def __init__(self, name):
        CLIError.__init__(self, "%(name)s is unexpected" % {
            "name": name
        })
        self.name = name


class ArgumentMissing(CLIError):
    pass


class UserTypeError(CLIError):
    pass


class CommandMissing(CLIError):
    pass


class EndOptionParsing(Exception):
    pass
