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
from itertools import takewhile, chain
from collections import deque

import six
from six import u
from six.moves import reduce

from awwparse.utils import (
    set_attributes_from_kwargs, force_list, get_terminal_width, golden_split,
    set_attributes, Signature, iter_mapping, create_repr, OrderedDict,
    ensure_all
)
from awwparse.exceptions import (
    CommandMissing, OptionConflict, CommandConflict, UnexpectedArgument,
    PositionalConflict, PositionalArgumentMissing, CLIError, EndOptionParsing
)

from awwparse.positionals import (
    String, Bytes, Integer, Float, Complex, Decimal, Any, Number, Choice,
    Positional, Boolean, NativeString, parse_positional_signature, Mapping,
    File, Resource, LocalResource
)
from awwparse.actions import store_last, append_to_list, add_to_set, add, sub


class Arguments(object):
    def __init__(self, arguments, application_name=None):
        self._arguments = iter(arguments)
        self._remaining = deque()
        if application_name is None:
            self.trace = [[]]
        else:
            self.trace = [[application_name], []]

    @property
    def current_frame(self):
        return self.trace[-1]

    def get_used(self, excluding=0):
        return list(chain.from_iterable(
            self.trace if excluding == 0 else self.trace[:-excluding]
        ))

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        if self._remaining:
            argument = self._remaining.popleft()
        else:
            argument = next(self._arguments)
        self.current_frame.append(argument)
        return argument

    def rewind(self):
        self._remaining.append(self.current_frame.pop())

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
            self.get_used()
        )


class CLIAttribute(object):
    def __init__(self, attribute, doc=None):
        self.attribute = attribute
        self.__doc__ = doc

    def __get__(self, instance, owner):
        if instance is None:
            return self
        try:
            return getattr(instance.parent, self.attribute)
        except AttributeError:
            raise AttributeError(self.attribute)


class Command(object):
    """
    Represents a command of a :class:`CLI` or another command.
    """
    #: A mapping of identifiers to options.
    options = []
    #: A mapping of command names to commands.
    commands = {}
    #: A positionals signature.
    positionals = ()
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
            if isinstance(annotation, Option):
                command.add_option(name, annotation)
            elif isinstance(annotation, Positional):
                if name in signature.defaults:
                    command.add_option(
                        name,
                        Option("-" + name[0], "--" + name, annotation),
                        resolve_conflicts=True
                    )
                else:
                    annotation.metavar = name
                    command.add_positional(annotation)
            else:
                raise ValueError(
                    "unexpected annotation: {0!r}".format(annotation)
                )
        if signature.arbitary_positional_arguments is not None:
            name = signature.arbitary_positional_arguments
            annotation = lookup_annotation(name)
            if isinstance(annotation, Positional):
                annotation.metavar = name
                annotation.remaining = True
                command.add_positional(annotation)
            else:
                raise ValueError(
                    "unexpected annotation: {0!r}".format(annotation)
                )
        for name in signature.keyword_arguments:
            annotation = lookup_annotation(name)
            if isinstance(annotation, Positional):
                command.add_option(
                    name,
                    Option("-" + name[0], "--" + name[1:], annotation),
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
    def from_function(cls, *positionals):
        """
        Takes optional :class:`~Positional` objects corresponding to the
        arguments in the signature of the function passed to the returned
        function which returns a :class:`Command` object for the given
        annotated function. The :class:`~Positional` objects serve as
        alternative to annotations which are not available in Python 2.x.

        Positional arguments are turned into arguments, keyword arguments are
        turned into options and arbitary positional arguments are turned into
        an argument that takes all remaining ones.

        Each argument has to be given an annotation. Allowed annotations are
        :class:`~awwparse.positionals.Positional` objects. For keyword
        arguments you can also provide an :class:`Option` object.

        If an annotation is missing or has a wrong type a :exc:`ValueError` is
        raised.
        """
        def decorate(function):
            signature = Signature.from_function(function)
            if not signature.annotations:
                signature.annotations = dict(zip(signature.names, positionals))
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
        return decorate

    @classmethod
    def from_method(cls, *positionals):
        """
        Like :meth:`from_function` but for methods.

        Note that for instance and class methods you have to pass the class or
        instance with the `default_args` argument of :meth:`run` to the method.
        """
        def decorate(method):
            signature = Signature.from_method(method)
            if not signature.annotations:
                method.__annotations__ = dict(zip(signature.names, positionals))
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
        return decorate

    def __init__(self, options=None, commands=None, positionals=None):
        self.options = OrderedDict()
        self.add_option("__awwparse_help", HelpOption())
        self.add_options(self.__class__.options)
        if options is not None:
            self.add_options(options)

        self.commands = OrderedDict()
        self.add_commands(self.__class__.commands)
        if commands is not None:
            self.add_commands(commands)

        self.positionals = parse_positional_signature(
            force_list(self.__class__.positionals),
            require_metavar=True
        )
        if positionals is not None:
            self.add_positionals(positionals)

        self.parent = None

        signature = Signature.from_method(self.main)
        if signature.annotations:
            self._populate_from_signature(self, signature)

        for name in dir(self):
            try:
                attribute = getattr(self, name)
            except AttributeError:
                # maybe raised by properties; can be safely ignored
                continue
            if isinstance(attribute, Command):
                if not isinstance(attribute.main, MethodType):
                    attribute.main = partial(attribute.main, self)
                self.add_command(name, attribute)

    stdin = CLIAttribute("stdin")
    stdout = CLIAttribute("stdout")
    stderr = CLIAttribute("stderr")
    exit = CLIAttribute("exit")
    width = CLIAttribute("width")
    section_indent = CLIAttribute("section_indent")

    @property
    def option_prefixes(self):
        """
        A set of all option name prefixes.
        """
        return set(option.name_prefix for option in self.options)

    @property
    def abbreviated_option_prefixes(self):
        """
        A set of all abbreviated option name prefixes.
        """
        return set(
            option.abbreviation_prefix for option in self.options
        )

    @property
    def option_shorts(self):
        """
        A mapping of all abbreviated option argument names to options.
        """
        return dict(
            (option.short, option) for option in self.options
            if option.short is not None
        )

    @property
    def option_longs(self):
        """
        A mapping of all complete option argument names to options.
        """
        return dict(
            (option.long, option) for option in self.options
            if option.long is not None
        )

    def get_usage(self, arguments=None):
        result = [] if arguments is None else arguments.get_used(1)
        if self.options:
            result.extend(
                u("[{0}]").format(option.get_usage()) for option in self.options
            )
        if self.commands:
            result.append(u("{%s}") % u(",").join(self.commands))
        if self.positionals:
            result.extend(positional.usage for positional in self.positionals)
        return u(" ").join(result)

    def add_option(self, identifier, option, force=False,
                   resolve_conflicts=False):
        """
        Adds the `option` with `identifier` to the command.

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
        option.setdefault_metavars(identifier)
        for conflicting, reason in conflicting_options:
            if reason == "short":
                if resolve_conflicts and option.long is not None:
                    option.short = None
                    continue
                if force:
                    self.remove_option(conflicting)
                    continue
            elif reason == "long":
                if resolve_conflicts and option.short is not None:
                    option.long = None
                    continue
                if force:
                    self.remove_option(conflicting)
                    continue
            raise OptionConflict(
                u("given option {0!r} conflicts with the {1} of {2!r}").format(
                    option, reason, conflicting
                )
            )
        self.options[option] = identifier

    def add_options(self, options, force=False, resolve_conflicts=False):
        """
        Adds `options` from a given mapping.
        """
        for identifier, option in iter_mapping(options):
            self.add_option(
                identifier, option, force=force,
                resolve_conflicts=resolve_conflicts
            )

    def remove_option(self, to_be_removed_option):
        """
        Removes the given option.
        """
        del self.options[to_be_removed_option]

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

    def add_positional(self, positional):
        """
        Adds the given `positional` to the command.

        May raise an :exc:`PositionalConflict` if last positional takes all
        remaining command line arguments - in which case the added positional
        would never be reached.
        """
        if positional.metavar is None:
            raise ValueError("metavar not set on: {0!r}".format(positional))
        if self.positionals and self.positionals[-1].remaining:
            raise PositionalConflict(
                u("last positional {0} takes all remaining arguments").format(
                    self.positionals[-1]
                )
            )
        self.positionals.append(positional)

    def add_positionals(self, positionals):
        """
        Adds `positionals` from a given iterable.
        """
        for positional in positionals:
            self.add_positional(positional)

    def copy(self):
        return self.__class__()

    def set_parent(self, parent):
        self.parent = parent

    def is_option(self, argument):
        return argument in self.option_shorts or argument in self.option_longs

    def is_command(self, argument):
        return argument in self.commands

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
        if self.positionals:
            self._print_positionals_help()
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

    def _print_positionals_help(self):
        self._print_columns(
            u("Positional Arguments"),
            (
                (positional.metavar, positional.help)
                for positional in self.positionals
            )
        )

    def _print_options_help(self):
        self._print_columns(
            u("Options"),
            (
                (option.get_usage(using="both"), option.help)
                for option in self.options
            )
        )

    def _print_commands_help(self):
        self._print_columns(
            u("Commands"),
            (
                ("{0} {1}".format(name, command.get_usage()), command.help)
                for name, command in self.commands.items()
            )
        )

    def get_match(self, argument):
        modified_argument = argument
        if self.is_command(argument):
            return argument, self.commands[argument], ""
        elif argument in self.option_longs:
            option = self.option_longs[argument]
            return self.options[option], option, ""
        elif argument in self.option_shorts:
            option = self.option_shorts[argument]
            return self.options[option], option, ""
        else:
            modified_argument = argument
            for option, name in self.options.items():
                matched, modified_argument = option.matches(modified_argument)
                if matched:
                    return name, option, modified_argument
        raise UnexpectedArgument(u("{0!r} is unexpected").format(argument))

    def run(self, arguments, default_args=None, default_kwargs=None,
            passthrough_errors=False):
        if not isinstance(arguments, Arguments):
            arguments = Arguments(arguments)
        expected_positionals = iter(self.positionals)
        args = [] if default_args is None else default_args
        kwargs = {}
        if default_kwargs:
            kwargs.update(default_kwargs)
        try:
            for argument in arguments:
                previous_modified = argument
                try:
                    name, match, modified = self.get_match(argument)
                except UnexpectedArgument:
                    exc_info = sys.exc_info()
                    try:
                        positional = next(expected_positionals)
                    except StopIteration:
                        six.reraise(*exc_info)
                    else:
                        arguments.rewind()
                        args = positional.parse_as_positional(
                            self, args, arguments
                        )
                else:
                    while modified != previous_modified:
                        if hasattr(match, "run"):
                            arguments.trace.append([])
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
                        u("expected {positional.metavar}").format(
                            positional=positional
                        )
                    )
        except CLIError:
            if passthrough_errors:
                raise
            self.handle_error(sys.exc_info(), arguments)
            assert False, "exit should have aborted execution"
        return self.main(*args, **kwargs)

    def handle_error(self, exc_info, arguments=None):
        exc_type, exc_value, traceback = exc_info
        try:
            self.stderr
        except AttributeError:
            six.reraise(exc_type, exc_value, traceback)
        self.print_error(exc_value)
        self.print_help(arguments)
        self.exit(exc_value.exit_code)

    def main(self, *args, **kwargs):
        if self.commands:
            # A quick hack to get exc_info for the exception. There is probably
            # a better way to do this.
            try:
                raise CommandMissing(u("expected a command"))
            except CommandMissing:
                self.handle_error(sys.exc_info())
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

    :param help: A help message explaining the option in detail
                 (default: ``None``).
    """
    prefix_chars = frozenset(["-", "+"])

    def __init__(self, *signature, **kwargs):
        short, long, positionals = self._parse_signature(signature)
        if short is None and long is None:
            raise TypeError("A short or a long has to be passed")
        if short is not None and len(short) != 2:
            raise ValueError("A short has to be two characters long")
        self.short = short
        self.long = long
        self.positionals = positionals
        set_attributes_from_kwargs(self, kwargs, {
            "action": store_last,
            "help": None
        })

    def _parse_signature(self, signature):
        if len(signature) < 2:
            raise TypeError(
                "expected at least 2 positional arguments"
                ", got {0}".format(len(signature))
            )

        short = long = None
        if isinstance(signature[0], str) and isinstance(signature[1], str):
            short = signature[0]
            long = signature[1]
            positionals = signature[2:]
        elif isinstance(signature[0], str):
            if len(signature[0]) == 2:
                short = signature[0]
            else:
                long = signature[0]
            positionals = signature[1:]
        else:
            raise TypeError(
                "expected short or long as first argument,"
                "got {0!r}".format(
                    signature[0]
                )
            )
        positionals = parse_positional_signature(positionals)
        if positionals[0].optional:
            raise ValueError(
                "first positional must not be optional: {0!r}".format(
                    positionals[0]
                )
            )
        return short, long, positionals

    def setdefault_metavars(self, metavar):
        if isinstance(metavar, six.binary_type):
            metavar = metavar.decode("utf-8")
        for positional in self.positionals:
            if positional.metavar is None:
                positional.metavar = metavar

    def copy(self):
        option = self.__class__.__new__(self.__class__)
        set_attributes(option, {
            "short": self.short,
            "long": self.long,
            "positionals": [
                positional.copy() for positional in self.positionals
            ],
            "action": self.action,
            "help": self.help
        })
        return option

    def get_usage(self, using="short"):
        if using not in set(["short", "long", "both"]):
            raise ValueError(
                "using has to be 'short', 'long' or 'both'; not %r" % using
            )
        # The usage is generated in three steps:
        # 1. A "linked list" is generated with lists as nodes. Each node is a
        #    list consisting of an optional positional as first item followed by
        #    zero or more required positionals, optionally followed by a list
        #    representing the next node.
        #
        # 2. The usage string is generated by enclosing the with a space joined
        #    usage strings of the positionals in a given node with brackets.
        #    The exception is the root which is not enclosed by brackets as the
        #    first node is always required.
        #
        # 3. The usage string generated in `2` is prefixed with the short and/
        #    or the long and either or both joined with a comma are returned.

        def step(acc, next):
            root, current = acc
            if next.optional:
                current.append([next])
                current = current[-1]
            else:
                current.append(next)
            return root, current

        def render(tree, _root=True):
            if isinstance(tree, Positional):
                return tree.usage
            else:
                nodes = u(" ").join(render(node, _root=False) for node in tree)
                if _root:
                    return nodes
                return u("[{0}]").format(nodes)

        usage = render(reduce(step, self.positionals, ([], ) * 2)[0])
        if using == "both" and self.short and self.long:
            return (
                u("{0} {1}").format(self.short, usage).strip() +
                u(", ") +
                u("{0} {1}").format(self.long, usage).strip()
            )
        else:
            return u("{0} {{0}}").format(
                self.short if using == "short" and self.short or
                              using in set(["long", "both"]) and not self.long
                else self.long
            ).format(usage)

        return usage.format(
            short=self.short,
            long=self.long,
            usage=render(reduce(step, self.positionals, ([], ) * 2)[0])
        ).strip()

    def get_prefix(self, argument):
        return "".join(takewhile(lambda c: c in self.prefix_chars, argument))

    def matches(self, argument):
        if argument == self.long:
            return True, ""
        elif self.short is not None and argument.startswith(self.short):
            prefix = self.get_prefix(self.short)
            stripped = argument.lstrip(self.short)
            modified = prefix + stripped if stripped else ""
            return True, modified
        return False, argument

    def parse(self, command, namespace, name, arguments):
        result = []
        for positional in self.positionals:
            try:
                result.append(positional.parse(command, arguments))
            except EndOptionParsing:
                break
        result = result if len(self.positionals) > 1 else result[0]
        namespace[name] = self.action(namespace.get(name), result)
        return namespace

    def __repr__(self):
        return create_repr(
            self.__class__.__name__,
            list(filter(None, [self.short, self.long])) + self.positionals,
            {
                "help": self.help
        })


class HelpOption(Option):
    def __init__(self):
        Option.__init__(
            self,
            "-h",
            "--help",
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

    def __init__(self, options=None, commands=None, positionals=None,
                 application_name=sys.argv[0], usage=None, stdin=sys.stdin,
                 stdout=sys.stdout, stderr=sys.stderr, exit=sys.exit,
                 width=None):
        Command.__init__(
            self, options=options, commands=commands, positionals=positionals
        )
        self.application_name = application_name
        self.usage = usage
        self.stdin = stdin
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
        arguments = Arguments(arguments, self.application_name)
        return Command.run(
            self, arguments, passthrough_errors=passthrough_errors
        )


__all__ = [
    "CLI", "Command", "Option", "Positional", "String", "Bytes", "Integer",
    "Float", "Complex", "Decimal", "Any", "Number", "Choice", "Boolean",
    "NativeString", "Mapping", "store_last", "append_to_list", "add_to_set",
    "add", "sub", "File", "Resource", "LocalResource"
]
# This should probably be a test, even though I think Python should raise an
# exception if __all__ is ill-defined, instead of ignoring it.
ensure_all(__all__)
