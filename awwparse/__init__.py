# coding: utf-8
"""
    awwparse
    ~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import sys
import textwrap
from collections import deque


from awwparse.utils import (
    set_attributes_from_kwargs, missing, force_list, get_terminal_width,
    golden_split
)
from awwparse.exceptions import (
    CommandMissing, OptionConflict, CommandConflict, UnexpectedArgument,
    ArgumentConflict, ArgumentMissing
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


class Arguments(object):
    def __init__(self, arguments):
        self._arguments = iter(arguments)
        self._remaining = deque()
        self.trace = []

    def __iter__(self):
        return self

    def next(self):
        if self._remaining:
            argument = self._remaining.popleft()
        else:
            argument = self._arguments.next()
        self.trace.append(argument)
        return argument

    def rewind(self):
        self._remaining.append(self.trace.pop())

    def __repr__(self):
        return "<%s(%r) %r>" % (
            self.__class__.__name__,
            self._arguments,
            self.trace
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


class Command(object):
    inherited_instance_attributes = frozenset(["stdin", "stdout", "stderr"])
    options = {}
    commands = {}
    arguments = ()
    help = None

    def __init__(self):
        self.options = self.options.copy()
        self.commands = {}
        for name, command in self.__class__.commands.iteritems():
            self.add_command(name, command.copy())
        self.arguments = parse_argument_signature(
            force_list(self.__class__.arguments)
        )
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

    @property
    def usage(self):
        result = []
        if self.options:
            result.extend(
                "[%s]" % option.get_usage(metavar=name)
                for name, option in sorted(
                    self.options.iteritems(),
                    key=lambda item: item[1].short is None
                )
            )
        if self.commands:
            result.append("{%s}" % ",".join(self.commands))
        if self.arguments:
            result.extend(argument.usage for argument in self.arguments)
        return " ".join(result)

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

    def add_argument(self, type):
        if self.arguments and self.arguments[-1].remaining:
            raise ArgumentConflict(
                "last argument %r takes all remaining arguments"
                % self.arguments[-1]
            )
        self.arguments.append(type)

    def __getattr__(self, name):
        if name in self.inherited_instance_attributes:
            return getattr(self.parent, name)
        raise AttributeError(name)

    def copy(self):
        return self.__class__()

    def set_parent(self, parent):
        self.parent = parent

    def is_option(self, argument):
        return argument in self.option_shorts or argument in self.option_longs

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

    def run(self, arguments, default_args=None, default_kwargs=None):
        arguments = Arguments(arguments)
        expected_positionals = iter(self.arguments)
        args = [] if default_args is None else default_args
        kwargs = self.defaults.copy()
        if default_kwargs is not None:
            kwargs.update(default_kwargs)
        for argument in arguments:
            previous_modified = argument
            try:
                name, match, modified = self.get_match(argument)
            except UnexpectedArgument as unexcepted_argument:
                try:
                    positional = expected_positionals.next()
                except StopIteration:
                    raise unexcepted_argument
                else:
                    arguments.rewind()
                    args.append(positional.parse(self, arguments))
            else:
                while modified != previous_modified:
                    if hasattr(match, "run"):
                        match.run(arguments, args, kwargs)
                        return
                    kwargs = match.parse(self, kwargs, name, arguments)
                    previous_modified = modified
                    if not modified:
                        break
                    name, option, modified = self.get_match(modified)
        try:
            positional = expected_positionals.next()
        except StopIteration:
            pass
        else:
            if not positional.optional:
                raise ArgumentMissing("expected %s" % positional.metavar)
        return self.main(*args, **kwargs)

    def main(self, *args, **kwargs):
        if self.commands:
            raise CommandMissing("expected a command")
        raise NotImplementedError()


class Argument(object):
    def __init__(self, type, metavar, default=missing, optional=False,
                 remaining=False, help=None):
        if isinstance(type, Type):
            self.type = type
        else:
            if not len(type) == 1:
                raise TypeError(type)
            self.type = type[0]
        self.metavar = metavar
        self.default = default
        self.optional = optional
        self.remaining = remaining
        self.help = help

    @property
    def metavar(self):
        return self.type.metavar

    @metavar.setter
    def metavar(self, new_metavar):
        self.type.metavar = new_metavar

    @property
    def default(self):
        return self.type.default

    @default.setter
    def default(self, new_default):
        self.type.default = new_default

    @property
    def optional(self):
        return self.type.optional

    @optional.setter
    def optional(self, new_optional):
        self.type.optional = new_optional

    @property
    def remaining(self):
        return self.type.remaining

    @remaining.setter
    def remaining(self, new_remaining):
        self.type.remaining = new_remaining

    @property
    def usage(self):
        if self.remaining:
            return "[%s ...]" % self.metavar
        elif self.optional:
            return "[%s]" % self.metavar
        return self.metavar

    def parse(self, command, arguments):
        return self.type.parse(command, arguments)

    def __repr__(self):
        return "%s(%r, %r, help=%r)" % (
            self.__class__.__name__,
            self.type,
            self.metavar,
            self.help
        )


class Option(object):
    """
    Represents how an application is supposed to do instead of the default
    behavior.
    """
    container_type = Last

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
            "help": None
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
            parser = self.container_type(*types)
            if parser.types[0].optional:
                raise ValueError(
                    "first type must not be optional: %r" % types[0]
                )
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

    def get_usage(self, using="short", metavar=None):
        if using not in {"short", "long", "both"}:
            raise ValueError(
                "using has to be 'short', 'long' or 'both'; not %r" % using
            )
        if using == "both" and self.short and self.long:
            caller = "%s, %s" % (self.short, self.long)
        elif (using == "short" and self.short or
              using in {"long", "both"} and not self.long):
            caller = self.short
        else:
            caller = self.long
        return "%s %s" % (
            caller,
            self.parser.get_usage(metavar or self.name or self.abbreviation)
        )

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
        return "%s(%s, %r, abbreviation_prefix=%r, name_prefix=%r, help=%r)" % (
            self.__class__.__name__,
            ", ".join(map(repr, filter(None, [self.abbreviation, self.name]))),
            self.parser,
            self.abbreviation_prefix,
            self.name_prefix,
            self.help
        )


class CLI(Command):
    """
    Represents the command line interface of an application.
    """
    section_indent = 2

    def __init__(self, application_name=sys.argv[0], usage=None,
                 stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
                 exit=sys.exit, width=None):
        Command.__init__(self)
        self.application_name = application_name
        self.usage = usage
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.exit = exit
        self.width = width if width is not None else get_terminal_width()

    @property
    def usage(self):
        if self._usage is None:
            return "%s %s" % (
                self.application_name,
                Command.usage.__get__(self)
            )
        return self._usage

    @usage.setter
    def usage(self, new_usage):
        self._usage = new_usage

    def _print_message(self, message, kind=None, stream=None):
        if kind is not None:
            message = "%s %s" % (kind, message)
        if stream is None:
            stream = self.stdout
        indent = " " * (len(kind) + 1) if kind else ""
        stream.write(
            "\n".join(
                textwrap.wrap(
                    message,
                    self.width,
                    subsequent_indent=indent,
                    break_long_words=False
                )
            ) + "\n"
        )

    def print_usage(self):
        self._print_message(self.usage, "USAGE:")

    def print_error(self, error):
        self._print_message(error, "ERROR:")

    def print_help(self):
        self.print_usage()
        self.stdout.write("\n")
        if self.help is not None:
            self._print_message(self.help)
        if self.arguments:
            self._print_arguments_help()
            if self.options or self.commands:
                self.stdout.write("\n")
        if self.options:
            self._print_options_help()
            if self.commands:
                self.stdout.write("\n")
        if self.commands:
            self._print_commands_help()

    def _print_columns(self, header, rows):
        self._print_message(header)
        usable_width = self.width - self.section_indent
        right_column_length, left_column_length = golden_split(usable_width)
        left_column_length -= 2 # padding
        output = []
        for left, right in rows:
            if right:
                wrapped = textwrap.wrap(
                    right,
                    right_column_length,
                    break_long_words=False
                )
            else:
                wrapped = []
            if len(left) > left_column_length:
                output.append(left)
            else:
                try:
                    first_line = wrapped.pop(0)
                except IndexError:
                    first_line = ""
                output.append(
                    ("%s%s" % (left.ljust(left_column_length), first_line))
                    .strip()
                )
            output.extend(wrapped)
        self.stdout.write("\n".join(
            "%s%s" % (" " * self.section_indent, line) for line in output
        ) + "\n")

    def _print_arguments_help(self):
        self._print_columns("Positional Arguments", (
            (argument.metavar, argument.help) for argument in self.arguments
        ))

    def _print_options_help(self):
        self._print_columns("Options", (
            (option.get_usage(using="both", metavar=name), option.help)
            for name, option in self.options.iteritems()
        ))

    def _print_commands_help(self):
        self._print_columns("Commands", (
            (name, command.help) for name, command in self.commands.iteritems()
        ))

    def run(self, arguments=sys.argv[1:]):
        return Command.run(self, arguments)
