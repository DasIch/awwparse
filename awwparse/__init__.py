# coding: utf-8
"""
    awwparse
    ~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import sys
from operator import attrgetter
from itertools import takewhile

from awwparse.utils import set_attributes_from_kwargs, missing
from awwparse.exceptions import (
    EndOptionParsing, CommandMissing, OptionConflict, CommandConflict,
    UnexpectedArgument
)

# imported for the API
from awwparse.types import (
    String, Bytes, Integer, Float, Complex, Decimal, Any, Number, Choice,
    parse_type_signature
)
# keeps pyflakes happy
assert (String, Bytes, Integer, Float, Complex, Decimal, Any, Number, Choice)


def store(namespace, name, result):
    namespace[name] = result
    return namespace


def append(namespace, name, result):
    namespace.setdefault(name, []).append(result)
    return namespace


def add(namespace, name, result):
    namespace.setdefault(name, set()).add(result)
    return namespace


class Action(object):
    inherited_instance_attributes = frozenset(["stdin", "stdout", "stderr"])
    options = {}
    commands = {}

    def __init__(self):
        self.options = self.options.copy()
        self.commands = {}
        for name, command in self.__class__.commands.iteritems():
            self.add_command(name, command.copy())
        self.parent = None

    def make_option_property(name, attrname, doc=None):
        def option_property(self):
            return {
                getattr(option, attrname)
                for option in self.options.itervalues()
            }
        option_property.__name__ = name
        option_property.__doc__ = doc
        return property(option_property)

    option_prefixes = make_option_property("option_prefixes", "name_prefix")
    abbreviated_option_prefixes = make_option_property(
        "abbreviated_option_prefixes",
        "abbreviation_prefix"
    )
    del make_option_property

    def make_option_dict_property(name, attrname, doc=None):
        def option_dict_property(self):
            return {
                getattr(option, attrname): option
                for option in self.options.itervalues()
            }
        option_dict_property.__name__ = name
        option_dict_property.__doc__ = doc
        return property(option_dict_property)

    option_shorts = make_option_dict_property("option_shorts", "short")
    option_longs = make_option_dict_property("option_longs", "long")
    del make_option_dict_property

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
        raise RuntimeError("no match: %r" % argument)

    def run(self, arguments, defaults=None):
        arguments = iter(arguments)
        namespace = self.defaults.copy()
        if defaults is not None:
            namespace.update(defaults)
        for argument in arguments:
            print argument
            if self.is_command(argument):
                print "is command"
                self.commands[argument].run(arguments, namespace)
                return
            elif self.is_long_option(argument):
                print "is long option"
                name, option, _ = self.get_match(argument)
                namespace = option.parse(self, namespace, name, arguments)
            elif self.is_short_option(argument):
                print "is short option"
                previous_modified = argument
                name, option, modified = self.get_match(argument)
                while modified != previous_modified:
                    namespace = option.parse(self, namespace, name, arguments)
                    previous_modified = modified
                    if not modified:
                        break
                    name, option, modified = self.get_match(modified)
            else:
                raise UnexpectedArgument("%r is unexpected" % argument)
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
        name, abbreviation, types = self._parse_signature(signature)
        if abbreviation is None and name is None:
            raise TypeError("An abbreviation or a name has to be passed")
        if abbreviation is not None and len(abbreviation) != 1:
            raise ValueError("An abbreviation has to be one character long")
        self.name = name
        self.abbreviation = abbreviation
        self.types = types
        set_attributes_from_kwargs(self, kwargs, {
            "abbreviation_prefix": "-",
            "name_prefix": "--",
            "action": store
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
        types = parse_type_signature(types)
        if types[0].optional:
            raise ValueError("first type must not be optional: %r" % types[0])
        return name, abbreviation, types

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
        if len(self.types) == 1:
            return self.types[0].default
        return map(
            attrgetter("default"),
            takewhile(
                lambda type: not type.optional and type.default is not missing,
                self.types
            )
        ) or missing

    def matches(self, argument):
        if argument == self.long:
            return True, ""
        elif self.short is not None and argument.startswith(self.short):
            stripped = argument.lstrip(self.short)
            modified = self.abbreviation_prefix + stripped if stripped else ""
            return True, modified
        return False, argument

    def parse(self, action, namespace, name, arguments):
        result = []
        for type in self.types:
            try:
                result.append(type.parse(action, arguments))
            except EndOptionParsing:
                break
        return self.action(
            namespace, name, result if len(self.types) > 1 else result[0]
        )


class Command(Action):
    """
    Represents what an application is supposed to do.
    """
    def __init__(self):
        Action.__init__(self)
        self.run_function = None

    def copy(self):
        new = self.__class__()
        new.run_function = self.run_function
        return new

    def main(self, **kwargs):
        if self.run_function is None:
            return Action.main(self, **kwargs)
        return self.run_function(self.parent, **kwargs)

    def __call__(self, func):
        self.run_function = func
        return self


class CLI(Action):
    """
    Represents the command line interface of an application.
    """
    def __init__(self, application_name=sys.argv[0], stdin=sys.stdin,
                 stdout=sys.stdout, stderr=sys.stderr, exit=sys.exit):
        Action.__init__(self)
        self.application_name = application_name
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.exit = exit

    def run(self, arguments=sys.argv[1:]):
        return Action.run(self, arguments)
