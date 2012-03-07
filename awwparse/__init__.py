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
from awwparse.exceptions import UnexpectedOption

# imported for the API
from awwparse.types import (
    String, Bytes, Integer, Float, Complex, Decimal, Any, Number, Choice
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


class Matcher(object):
    def matches(self, argument):
        return False, ""


class Parser(object):
    def parse(self, action, namespace, name, arguments):
        raise NotImplementedError()


class ActionMeta(type):
    def __init__(self, name, bases, attributes):
        type.__init__(self, name, bases, attributes)
        self.matchers = {}
        self.actions = {}
        for name, attribute in attributes.iteritems():
            if isinstance(attribute, Matcher):
                self.matchers[name] = attribute
                if not isinstance(attribute, Parser):
                    self.actions[name] = attribute

    def __setattr__(self, name, attribute):
        type.__setattr__(self, name, attribute)
        if isinstance(attribute, Matcher):
            self.matchers[name] = attribute
            self.actions.pop(name, None)

    def __delattr__(self, name):
        type.__delattr__(self, name)
        self.matchers.pop(name, None)
        self.actions.pop(name, None)


class Action(object):
    __metaclass__ = ActionMeta

    inherited_instance_attributes = frozenset(["stdin", "stdout", "stderr"])

    def __init__(self):
        self.matchers = self.matchers.copy()
        actions = {}
        for name, action in self.actions.iteritems():
            action = action.copy()
            action.parent = self
            self.matchers[name] = actions = action
        self.actions = actions
        self.parent = None

    @property
    def options(self):
        return {
            name: matcher for name, matcher in self.matchers.iteritems()
            if isinstance(matcher, Option)
        }

    @property
    def option_prefixes(self):
        return {option.name_prefix for option in self.options.itervalues()}

    @property
    def abbreviated_option_prefixes(self):
        return {
            option.abbreviation_prefix for option in self.options.itervalues()
        }

    @property
    def defaults(self):
        return {
            name: option.default for name, option in self.options.iteritems()
            if option.default is not missing
        }

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

    is_short_option = make_is_option("is_short_option", "option_prefixes")
    is_long_option = make_is_option(
        "is_long_option", "abbreviated_option_prefixes"
    )
    del make_is_option

    def is_option(self, argument):
        return self.is_short_option(argument) or self.is_long_option(argument)

    def is_command(self, argument):
        for _, matcher, _ in self.get_matches(argument):
            if isinstance(matcher, Command):
                return True
        return False

    def strip_prefix(self, argument):
        prefixes = self.option_prefixes | self.abbreviated_option_prefixes
        for prefix in prefixes:
            if argument.startswith(prefix):
                return argument.lstrip(prefix)
        return argument

    def get_matches(self, argument):
        modified_argument = argument
        for name, matcher in self.matchers.iteritems():
            matched, modified_argument = matcher.matches(modified_argument)
            if matched:
                yield name, matcher, modified_argument

    def parse(self, arguments):
        arguments = iter(arguments)
        for argument in arguments:
            if self.is_long_option(argument):
                try:
                    name, option, _ = self.get_matches(argument).next()
                except StopIteration:
                    raise UnexpectedOption(argument)
                else:
                    yield name, option
            elif self.is_short_option(argument):
                for name, option, modified in self.get_matches(argument):
                    yield name, option
                if modified:
                    raise UnexpectedOption(
                        argument, self.strip_prefix(modified)[0]
                    )
            elif self.is_command(argument):
                name, command, _ = self.get_matches(argument).next()
                yield name, command
                raise StopIteration("encountered command")

    def run(self, arguments, defaults=None):
        arguments = iter(arguments)
        namespace = self.defaults.copy()
        if defaults is not None:
            namespace.update(defaults)
        for name, parsed in self.parse(arguments):
            if isinstance(parsed, Parser):
                namespace = parsed.parse(self, namespace, name, arguments)
            else:
                parsed.run(arguments, namespace)
                return None
        return namespace


class Option(Matcher, Parser):
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

        def resolve_optionals(types, root=False):
            result = []
            if not root:
                types[0].optional = True
            for type in types:
                if isinstance(type, list):
                    result.extend(resolve_optionals(type))
                else:
                    result.append(type)
            return result

        name = abbreviation = None
        if isinstance(signature[0], str):
            if len(signature[0]) == 1:
                abbreviation = signature[0]
                if isinstance(signature[1], str):
                    name = signature[1]
                    types = signature[2:]
            else:
                name = signature[0]
                types = signature[1:]
        else:
            raise TypeError(
                "expected str as first argument, got %r" % signature[0]
            )
        return name, abbreviation, resolve_optionals(types, root=True)

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
        if argument.startswith(self.abbreviation_prefix):
            options = list(argument[len(self.abbreviation_prefix):])
            try:
                options.remove(self.abbreviation)
            except ValueError:
                return False, argument
            else:
                if options:
                    return True, self.abbreviation_prefix + "".join(options)
                else:
                    return True, ""
        return False, argument

    def parse(self, action, namespace, name, arguments):
        result = []
        for type in self.types:
            result.append(type.parse(action, arguments))
        return self.action(
            namespace, name, result if len(self.types) > 1 else result[0]
        )


class Command(Action, Matcher):
    """
    Represents what an application is supposed to do.
    """
    def __init__(self, name):
        Action.__init__(self)
        self.name = name
        self.run_function = None

    def matches(self, argument):
        return argument == self.name, ""

    def copy(self):
        new = self.__class__(self.name)
        new.run_function = self.run_function
        return new

    def run(self, arguments, defaults=None):
        if self.run_function is None:
            raise RuntimeError("run_function unspecified")
        return self.run_function(
            self.parent,
            **Action.run(self, arguments, defaults)
        )

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
        result = Action.run(self, arguments)
        # if a command was triggered the result is None and we don't want to
        # call main
        if result is not None:
            return self.main(**result)

    def main(self, **kwargs):
        # TODO: fail with a missing command exception
        raise NotImplementedError()
