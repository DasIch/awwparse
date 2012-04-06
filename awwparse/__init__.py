# coding: utf-8
"""
    awwparse
    ~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
from __future__ import absolute_import
import sys
import textwrap
from types import MethodType
from functools import partial
from collections import deque

from six import u

from awwparse.utils import (
    set_attributes_from_kwargs, missing, force_list, get_terminal_width,
    golden_split, set_attributes, Signature, iter_mapping, create_repr
)
from awwparse.exceptions import (
    CommandMissing, OptionConflict, CommandConflict, UnexpectedArgument,
    ArgumentConflict, PositionalArgumentMissing, CLIError
)

from awwparse.arguments import (
    String, Bytes, Integer, Float, Complex, Decimal, Any, Number, Choice,
    Argument, Boolean, Last, List, Set, Adder, ContainerArgument, NativeString,
    parse_argument_signature, Mapping
)


class Arguments(object):
    def __init__(self, arguments):
        self._arguments = iter(arguments)
        self._remaining = deque()
        self.trace = []

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        if self._remaining:
            argument = self._remaining.popleft()
        else:
            argument = next(self._arguments)
        self.trace.append(argument)
        return argument

    def rewind(self):
        self._remaining.append(self.trace.pop())

    def __nonzero__(self):
        try:
            self.next()
        except StopIteration:
            return False
        self.rewind()
        return True

    def __bool__(self):
        return self.__nonzero__()

    def __repr__(self):
        return "<{0}({1!r}) {2!r}>".format(
            self.__class__.__name__,
            self._arguments,
            self.trace
        )


class Command(object):
    """
    Represents a command of a :class:`CLI` or another command.
    """
    inherited_instance_attributes = frozenset([
        "stdout", "stderr", "exit", "width", "section_indent"
    ])
    #: A mapping of option names to options.
    options = []
    #: A mapping of command names to commands.
    commands = {}
    #: An arguments signature.
    arguments = ()
    #: A help message explaining this command.
    help = None

    @classmethod
    def _populate_from_signature(cls, command, signature):
        def lookup_annotation(name):
            try:
                return signature.annotations[name]
            except KeyError:
                raise ValueError("missing annotation for: {0}".format(name))
        for name in signature.positional_arguments:
            annotation = lookup_annotation(name)
            if isinstance(annotation, (Argument, ContainerArgument)):
                annotation.metavar = name
                command.add_argument(annotation)
            else:
                raise ValueError(
                    "unexpected annotation: {0!r}".format(annotation)
                )
        if signature.arbitary_positional_arguments is not None:
            name = signature.arbitary_positional_arguments
            annotation = lookup_annotation(name)
            if isinstance(annotation, (Argument, ContainerArgument)):
                annotation.metavar = name
                annotation.remaining = True
                command.add_argument(annotation)
            else:
                raise ValueError(
                    "unexpected annotation: {0!r}".format(annotation)
                )
        for name in signature.keyword_arguments:
            annotation = lookup_annotation(name)
            if isinstance(annotation, (Argument, ContainerArgument)):
                command.add_option(
                    name,
                    Option(name[0], name[1:], annotation),
                    resolve_conflicts=True
                )
            elif isinstance(annotation, Option):
                command.add_option(name, annotation)
            else:
                raise ValueError(
                    "unexcepted annotation: {0!r}".format(annotation)
                )
        command.help = signature.documentation
        return command

    @classmethod
    def from_function(cls, function):
        """
        Returns a :class:`Command` object for the given annotated function.

        Positional arguments are turned into arguments, keyword arguments are
        turned into options and arbitary positional arguments are turned into
        an argument that takes all remaining ones.

        Each argument has to be given an annotation. Allowed annotations are
        :class:`~awwparse.arguments.Argument` objects and
        :class:`~awwparse.arguments.ContainerArgument` objects. For keyword
        arguments you can also provide an :class:`Option` object.

        If an annotation is missing or has a wrong type a :exc:`ValueError` is
        raised.
        """
        signature = Signature.from_function(function)
        command = type(
            function.__name__,
            (cls, ),
            {
                "__module__": function.__module__,
                "__doc__": function.__doc__
            }
        )()
        command.main = function
        cls._populate_from_signature(command, signature)
        return command

    @classmethod
    def from_method(cls, method):
        """
        Like :meth:`from_function` but for methods.

        Note that for instance and class methods you have to pass the class or
        instance with the `default_args` argument of :meth:`run` to the method.
        """
        command = type(
            method.__name__,
            (cls, ),
            {
                "__module__": method.__module__,
                "__doc__": method.__doc__,
                "main": staticmethod(method)
            }
        )()
        return command

    def __init__(self, options=None, commands=None, arguments=None):
        self.options = [
            ("__awwparse_help", HelpOption())
        ]
        self.add_options(self.__class__.options)
        if options is not None:
            self.add_options(options)

        self.commands = {}
        self.add_commands(self.__class__.commands)
        if commands is not None:
            self.add_commands(commands)

        self.arguments = parse_argument_signature(
            force_list(self.__class__.arguments),
            require_metavar=True
        )
        if arguments is not None:
            self.add_arguments(arguments)

        self.parent = None

        signature = Signature.from_method(self.main)
        if signature.annotations:
            self._populate_from_signature(self, signature)

        for name in dir(self):
            attribute = getattr(self, name)
            if isinstance(attribute, Command):
                if not isinstance(attribute.main, MethodType):
                    attribute.main = partial(attribute.main, self)
                self.add_command(name, attribute)

    @property
    def option_prefixes(self):
        """
        A set of all option name prefixes.
        """
        return set(option.name_prefix for (_, option) in self.options)

    @property
    def abbreviated_option_prefixes(self):
        """
        A set of all abbreviated option name prefixes.
        """
        return set(
            option.abbreviation_prefix for (_, option) in self.options
        )

    @property
    def option_shorts(self):
        """
        A mapping of all abbreviated option argument names to options.
        """
        return dict(
            (option.short, option) for (_, option) in self.options
            if option.short is not None
        )

    @property
    def option_longs(self):
        """
        A mapping of all complete option argument names to options.
        """
        return dict(
            (option.long, option) for (_, option) in self.options
            if option.long is not None
        )

    @property
    def defaults(self):
        """
        A mapping of option names to option default values.
        """
        return dict(
            (name, option.default) for name, option in self.options
            if option.default is not missing
        )

    def get_usage(self, arguments=None):
        result = [] if arguments is None else arguments.trace[:-1]
        if self.options:
            result.extend(
                u("[{0}]").format(option.get_usage())
                for option in sorted(
                    (option for (_, option) in self.options),
                    key=lambda option: option.short is None
                )
            )
        if self.commands:
            result.append(u("{%s}") % u(",").join(self.commands))
        if self.arguments:
            result.extend(argument.usage for argument in self.arguments)
        return u(" ").join(result)

    def add_option(self, name, option, force=False, resolve_conflicts=False):
        """
        Adds the `option` with `name` to the command.

        May raise an :exc:`OptionConflict` exception if the option name or it's
        abbreviation is  identical to those of another option. If `force` is
        ``True`` it will ignore the latter kind of conflict and replace the old
        option with the given one.  If `resolve_conflicts` is ``True``
        conflicts on argument names and abbreviations thereof will be resolved
        if possible by removing conflicting attributes.
        """
        conflicting_options = []
        if option.short in self.option_shorts:
            conflicting_options.append(
                (self.option_shorts[option.short], "short")
            )
        if option.long in self.option_longs:
            conflicting_options.append(
                (self.option_longs[option.long], "long")
            )
        option = option.copy()
        option.setdefault_metavars(name)
        for conflicting, reason in conflicting_options:
            if reason == "short":
                if resolve_conflicts and option.long is not None:
                    option.abbreviation = None
                    continue
                if force:
                    self.remove_option(conflicting)
                    continue
            elif reason == "long":
                if resolve_conflicts and option.short is not None:
                    option.name = None
                    continue
                if force:
                    self.remove_option(conflicting)
                    continue
            raise OptionConflict(
                u("given option {0!r} conflicts with the {1} of {2!r}").format(
                    option, reason, conflicting
                )
            )
        self.options.append((name, option))

    def add_options(self, options, force=False, resolve_conflicts=False):
        """
        Adds `options` from a given mapping.
        """
        for name, option in iter_mapping(options):
            self.add_option(
                name, option, force=force, resolve_conflicts=resolve_conflicts
            )

    def remove_option(self, to_be_removed_option):
        """
        Removes the given option.
        """
        self.options = [
            (name, option) for name, option in self.options
            if option is not to_be_removed_option
        ]

    def add_command(self, name, command, force=False):
        """
        Add the `command` with `name` to the command.

        May raise a :exc:`CommandConflict` if `name` is identical to that of
        another command unless `force` is ``True`` in which case the given
        `command` overwrites the confliciting one.
        """
        if not force and name in self.commands:
            raise CommandConflict(
                u("given command {0!r} conflicts with {1!r}").format(
                    command, self.commands[name]
                )
            )
        command.parent = self
        self.commands[name] = command

    def add_commands(self, commands, force=False):
        """
        Adds `commands` from a given mapping.
        """
        for name, command in iter_mapping(commands):
            self.add_command(name, command)

    def add_argument(self, argument):
        """
        Adds the given `argument` to the command.

        May raise an :exc:`ArgumentConflict` if last argument takes all
        remaining command line arguments - in which case the added argument
        would never be reached.
        """
        if argument.metavar is None:
            raise ValueError("metavar not set on: {0!r}".format(argument))
        if self.arguments and self.arguments[-1].remaining:
            raise ArgumentConflict(
                u("last argument {0} takes all remaining arguments").format(
                    self.arguments[-1]
                )
            )
        self.arguments.append(argument)

    def add_arguments(self, arguments):
        """
        Adds `arguments` from a given iterable.
        """
        for argument in arguments:
            self.add_argument(argument)

    def __getattr__(self, name):
        missing = object()
        if name in self.inherited_instance_attributes:
            attribute =  getattr(self.parent, name, missing)
            if attribute is not missing:
                return attribute
        raise AttributeError(
            "{0!r} object has no attribute {1!r}".format(
                self.__class__.__name__, name
            )
        )

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

    def _print_message(self, message, prefix=None, stream=None):
        if prefix is not None:
            message = u("{0}{1}").format(prefix, message)
        if stream is None:
            stream = self.stdout
        indent = u(" ") * len(prefix) if prefix else u("")
        stream.write(
            u("\n").join(
                textwrap.wrap(
                    message,
                    self.width,
                    subsequent_indent=indent,
                    break_long_words=False
                )
            ) + u("\n")
        )

    def _print_newline(self, stream=None):
        if stream is None:
            stream = self.stdout
        stream.write(u("\n"))

    def print_usage(self, arguments=None):
        self._print_message(self.get_usage(arguments), prefix=u("Usage: "))

    def print_error(self, error):
        self._print_message(error, prefix=u("Error: "), stream=self.stderr)

    def print_help(self, arguments=None):
        self.print_usage(arguments)
        self._print_newline()
        if self.help is not None:
            self._print_message(self.help)
        if self.arguments:
            self._print_arguments_help()
            if self.options or self.commands:
                self._print_newline()
        if self.options:
            self._print_options_help()
            if self.commands:
                self._print_newline()
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
                    first_line = u("")
                output.append(
                    u("{0}{1}")
                    .format(left.ljust(left_column_length), first_line)
                    .strip()
                )
            output.extend(wrapped)
        self.stdout.write(u("\n").join(
            u("{0}{1}").format(u(" ") * self.section_indent, line)
            for line in output
        ) + u("\n"))

    def _print_arguments_help(self):
        self._print_columns(
            u("Positional Arguments"),
            ((argument.metavar, argument.help) for argument in self.arguments)
        )

    def _print_options_help(self):
        self._print_columns(
            u("Options"),
            (
                (option.get_usage(using="both"), option.help)
                for (_, option) in self.options
            )
        )

    def _print_commands_help(self):
        self._print_columns(
            u("Commands"),
            (
                (name, command.help)
                for name, command in self.commands.items()
            )
        )

    def get_match(self, argument):
        modified_argument = argument
        if self.is_command(argument):
            return argument, self.commands[argument], ""
        else:
            modified_argument = argument
            for name, option in self.options:
                matched, modified_argument = option.matches(modified_argument)
                if matched:
                    return name, option, modified_argument
        raise UnexpectedArgument(u("{0!r} is unexpected").format(argument))

    def run(self, arguments, default_args=None, default_kwargs=None,
            passthrough_errors=False):
        if not isinstance(arguments, Arguments):
            arguments = Arguments(arguments)
        expected_positionals = iter(self.arguments)
        args = [] if default_args is None else default_args
        kwargs = self.defaults.copy()
        if default_kwargs:
            kwargs.update(default_kwargs)
        try:
            for argument in arguments:
                previous_modified = argument
                try:
                    name, match, modified = self.get_match(argument)
                except UnexpectedArgument as unexcepted_argument:
                    try:
                        positional = next(expected_positionals)
                    except StopIteration:
                        raise unexcepted_argument
                    else:
                        arguments.rewind()
                        args = positional.parse_as_positional(
                            self, args, arguments
                        )
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
                positional = next(expected_positionals)
            except StopIteration:
                pass
            else:
                if not positional.optional:
                    raise PositionalArgumentMissing(
                        u("expected {option.metavar}").format(
                            option=positional
                        )
                    )
        except CLIError as error:
            if passthrough_errors:
                raise
            self.handle_error(error, arguments)
            assert False, "exit should have aborted execution"
        return self.main(*args, **kwargs)

    def handle_error(self, error, arguments=None):
        try:
            self.stderr
        except AttributeError:
            raise error
        self.print_error(error)
        self.print_help(arguments)
        self.exit(error.exit_code)

    def main(self, *args, **kwargs):
        if self.commands:
            self.handle_error(CommandMissing(u("expected a command")))
        else:
            raise NotImplementedError(
                "{0}.main(*{1!r}, **{2!r})".format(
                    self.__class__.__name__,
                    args,
                    kwargs
                )
            )


class Option(object):
    """
    Represents an option of the :class:`CLI` or a :class:`Command` e.g.
    ``--option``.

    Takes a single character as abbreviated option name or the complete option
    name or both (in that order) followed by an argument signature.

    Other optional parameters are:

    :param abbreviation_prefix: Prefix used for abbreviated option names
                                (default: ``"-"``).
    :param name_prefix: Prefix used for option names (default: ``"--"``).
    :param help: A help message explaining the option in detail
                 (default: ``None``).
    """
    container_argument = Last

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
                ", got {0}".format(len(signature))
            )

        name = abbreviation = None
        if isinstance(signature[0], str) and isinstance(signature[1], str):
            abbreviation = signature[0]
            name = signature[1]
            arguments = signature[2:]
        elif isinstance(signature[0], str):
            if len(signature[0]) == 1:
                abbreviation = signature[0]
            else:
                name = signature[0]
            arguments = signature[1:]
        else:
            raise TypeError(
                "expected name or abbreviation as first argument,"
                "got {0!r}".format(
                    signature[0]
                )
            )
        if len(arguments) == 1 and isinstance(arguments[0], ContainerArgument):
            parser = arguments[0]
        else:
            parser = self.container_argument(*arguments)
            if parser.arguments[0].optional:
                raise ValueError(
                    "first argument must not be optional: {0!r}".format(
                        arguments[0]
                    )
                )
        return name, abbreviation, parser

    @property
    def short(self):
        """
        The abbreviated option name including prefix.
        """
        if self.abbreviation is None:
            return None
        return self.abbreviation_prefix + self.abbreviation

    @property
    def long(self):
        """
        The option name including prefix.
        """
        if self.name is None:
            return None
        return self.name_prefix + self.name

    @property
    def default(self):
        """
        The default value for this option.
        """
        return self.parser.default

    def setdefault_metavars(self, metavar):
        self.parser.setdefault_metavars(metavar)

    def copy(self):
        option = self.__class__.__new__(self.__class__)
        set_attributes(option, {
            "name": self.name,
            "abbreviation": self.abbreviation,
            "parser": self.parser.copy(),
            "abbreviation_prefix": self.abbreviation_prefix,
            "name_prefix": self.name_prefix,
            "help": self.help
        })
        return option

    def get_usage(self, using="short"):
        if using not in set(["short", "long", "both"]):
            raise ValueError(
                "using has to be 'short', 'long' or 'both'; not %r" % using
            )
        if using == "both" and self.short and self.long:
            return u("{short} {usage}, {long} {usage}").format(
                short=self.short,
                long=self.long,
                usage=self.parser.usage
            ).strip()
        return u("{0} {1}").format(
            self.short if using == "short" and self.short or
                          using in set(["long", "both"]) and not self.long
            else self.long,
            self.parser.usage
        ).strip()

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
        return create_repr(
            self.__class__.__name__,
            list(filter(None, [self.abbreviation, self.name])) + [self.parser],
            {
                "abbreviation_prefix": self.abbreviation_prefix,
                "name_prefix": self.name_prefix,
                "help": self.help
        })


class HelpOption(Option):
    def __init__(self):
        Option.__init__(
            self,
            "h",
            "help",
            NativeString(remaining=True),
            help=u("Show this message")
        )

    def get_usage(self, using="short"):
        allowed = frozenset(["short", "long", "both"])
        if using not in allowed:
            raise ValueError(
                "using has to be {allowed}; not {using_arg!r}".format(
                    allowed=allowed,
                    using_arg=using
                )
            )
        if using == "short":
            return self.short
        elif using == "long":
            return self.long
        else:
            return u("{0}, {1}").format(self.short, self.long)

    def parse(self, command, namespace, name, arguments):
        command.print_help(arguments)
        command.exit()

    def __repr__(self):
        return "{0}()".format(self.__class__.__name__)


class CLI(Command):
    """
    Represents the command line interface of an application. Inherits from
    :class:`Command`.
    """
    #: The number of spaces used for indentation of sections in the help
    #: message (default: 2).
    section_indent = 2

    def __init__(self, options=None, commands=None, arguments=None,
                 application_name=sys.argv[0], usage=None, stdout=sys.stdout,
                 stderr=sys.stderr, exit=sys.exit, width=None):
        Command.__init__(
            self, options=options, commands=commands, arguments=arguments
        )
        self.application_name = application_name
        self.usage = usage
        self.stdout = stdout
        self.stderr = stderr
        self.exit = exit
        self.width = width if width is not None else get_terminal_width()

    def get_usage(self, arguments=None):
        if self.usage is None:
            return u("{0} {1}").format(
                self.application_name,
                Command.get_usage(self)
            )
        return self.usage

    def run(self, arguments=sys.argv[1:], passthrough_errors=False):
        """run(self, arguments=sys.argv[1:], passthrough_errors=False)

        Parses the given `arguments` (default: ``sys.argv[1:]`` and invokes
        :meth:`main()` with the result.

        If `passthrough_errors` (default: ``False``) is ``True``
        :exc:`CLIError`\s will not be caught.
        """
        arguments = Arguments(arguments)
        arguments.trace.append(self.application_name)
        return Command.run(
            self, arguments, passthrough_errors=passthrough_errors
        )


__all__ = [
    "CLI", "Command", "Option", "Argument", "String", "Bytes", "Integer",
    "Float", "Complex", "Decimal", "Any", "Number", "Choice", "Boolean",
    "Last", "List", "Set", "Adder", "NativeString", "Mapping"
]
