# coding: utf-8
"""
    awwparse
    ~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import sys

from awwparse.utils import set_attributes_from_kwargs, missing
from awwparse.exceptions import (
    CommandMissing, OptionConflict, CommandConflict, UnexpectedArgument
)

# imported for the API
from awwparse.types import (
    String, Bytes, Integer, Float, Complex, Decimal, Any, Number, Choice,
    Type, Boolean, Last, List, Set, Adder, ContainerType
)
# keeps pyflakes happy
assert (
    String, Bytes, Integer, Float, Complex, Decimal, Any, Number, Choice, Type,
    Boolean, Last, List, Set, Adder
)


class Command(object):
    inherited_instance_attributes = frozenset(["stdin", "stdout", "stderr"])
    options = {}
    commands = {}

    def __init__(self):
        self.options = self.options.copy()
        self.commands = {}
        for name, command in self.__class__.commands.iteritems():
            self.add_command(name, command.copy())
        self.parent = None

    @property
    def option_prefixes(self):
        return {option.name_prefix for option in self.options.itervalues()}

    @property
    def abbreviated_option_prefixes(self):
        return {
            option.abbreviation_prefix for option in self.options.itervalues()
        }

    @property
    def option_shorts(self):
        return {
            option.short: option for option in self.options.itervalues()
            if option.short is not None
        }

    @property
    def option_longs(self):
        return {
            option.long: option for option in self.options.itervalues()
            if option.long is not None
        }

    @property
    def defaults(self):
        return {
            name: option.default for name, option in self.options.iteritems()
            if option.default is not missing
        }

    def add_option(self, name, option, force=False):
        arguments = None
        if option.short in self.option_shorts:
            arguments = option, self.option_shorts[option.short], "short"
        elif option.long in self.option_longs:
            arguments = option, self.option_longs[option.long], "long"
        elif not force and name in self.options:
            arguments = option, self.options[name], "name"
        if arguments:
            raise OptionConflict(
                "given option %r conflicts with %r on %r" % arguments
            )
        self.options[name] = option

    def add_command(self, name, command, force=False):
        if not force and name in self.commands:
            raise CommandConflict("given command %r conflicts with %r" % (
                command, self.commands[name]
            ))
        command.parent = self
        self.commands[name] = command

    def __getattr__(self, name):
        if name in self.inherited_instance_attributes:
            return getattr(self.parent, name)
        raise AttributeError(name)

    def copy(self):
        return self.__class__()

    def set_parent(self, parent):
        self.parent = parent

    def make_is_option(name, attrname, doc=None):
        def is_option(self, argument):
            return any(
                argument.startswith(p) for p in getattr(self, attrname)
            ) or getattr(self.parent, name, lambda arg: False)(argument)
        is_option.__name__ = name
        is_option.__doc__ = doc
        return is_option

    is_short_option = make_is_option(
        "is_short_option",
        "abbreviated_option_prefixes"
    )
    is_long_option = make_is_option(
        "is_long_option",
        "option_prefixes"
    )
    del make_is_option

    def is_option(self, argument):
        return self.is_short_option(argument) or self.is_long_option(argument)

    def is_command(self, argument):
        return argument in self.commands

    def strip_prefix(self, argument):
        prefixes = self.option_prefixes | self.abbreviated_option_prefixes
        for prefix in prefixes:
            if argument.startswith(prefix):
                return argument.lstrip(prefix)
        return argument

    def get_match(self, argument):
        modified_argument = argument
        if self.is_command(argument):
            return argument, self.commands[argument], ""
        else:
            modified_argument = argument
            for name, option in self.options.iteritems():
                matched, modified_argument = option.matches(modified_argument)
                if matched:
                    return name, option, modified_argument
        raise UnexpectedArgument("%r is unexpected" % argument)

    def run(self, arguments, defaults=None):
        arguments = iter(arguments)
        namespace = self.defaults.copy()
        if defaults is not None:
            namespace.update(defaults)
        for argument in arguments:
            previous_modified = argument
            name, match, modified = self.get_match(argument)
            while modified != previous_modified:
                if hasattr(match, "run"):
                    match.run(arguments, namespace)
                    return
                namespace = match.parse(self, namespace, name, arguments)
                previous_modified = modified
                if not modified:
                    break
                name, option, modified = self.get_match(modified)
        return self.main(**namespace)

    def main(self, **kwargs):
        if self.commands:
            raise CommandMissing("expected a command")
        raise NotImplementedError()


class Option(object):
    """
    Represents how an application is supposed to do instead of the default
    behavior.
    """
    def __init__(self, *signature, **kwargs):
        name, abbreviation, parser = self._parse_signature(signature)
        if abbreviation is None and name is None:
            raise TypeError("An abbreviation or a name has to be passed")
        if abbreviation is not None and len(abbreviation) != 1:
            raise ValueError("An abbreviation has to be one character long")
        self.name = name
        self.abbreviation = abbreviation
        self.parser = parser
        set_attributes_from_kwargs(self, kwargs, {
            "abbreviation_prefix": "-",
            "name_prefix": "--",
        })

    def _parse_signature(self, signature):
        if len(signature) < 2:
            raise TypeError(
                "expected at least 2 positional arguments"
                ", got %d" % len(signature)
            )

        name = abbreviation = None
        if isinstance(signature[0], str) and isinstance(signature[1], str):
            abbreviation = signature[0]
            name = signature[1]
            types = signature[2:]
        elif isinstance(signature[0], str):
            if len(signature[0]) == 1:
                abbreviation = signature[0]
            else:
                name = signature[0]
            types = signature[1:]
        else:
            raise TypeError(
                "expected name or abbreviation as first argument, got %r"
                % signature[0]
            )
        if len(types) == 1 and isinstance(types[0], ContainerType):
            parser = types[0]
        else:
            parser = Last(*types)
            if parser.types[0].optional:
                raise ValueError("first type must not be optional: %r" % types[0])
        return name, abbreviation, parser

    @property
    def short(self):
        if self.abbreviation is None:
            return None
        return self.abbreviation_prefix + self.abbreviation

    @property
    def long(self):
        if self.name is None:
            return None
        return self.name_prefix + self.name

    @property
    def default(self):
        return self.parser.default

    def matches(self, argument):
        if argument == self.long:
            return True, ""
        elif self.short is not None and argument.startswith(self.short):
            stripped = argument.lstrip(self.short)
            modified = self.abbreviation_prefix + stripped if stripped else ""
            return True, modified
        return False, argument

    def parse(self, command, namespace, name, arguments):
        return self.parser.parse_and_store(command, namespace, name, arguments)

    def __repr__(self):
        return "%s(%s, %r, abbreviation_prefix=%r, name_prefix=%r)" % (
            self.__class__.__name__,
            ", ".join(map(repr, filter(None, [self.abbreviation, self.name]))),
            self.parser,
            self.abbreviation_prefix,
            self.name_prefix
        )


class CLI(Command):
    """
    Represents the command line interface of an application.
    """
    def __init__(self, application_name=sys.argv[0], stdin=sys.stdin,
                 stdout=sys.stdout, stderr=sys.stderr, exit=sys.exit):
        Command.__init__(self)
        self.application_name = application_name
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.exit = exit

    def run(self, arguments=sys.argv[1:]):
        return Command.run(self, arguments)
