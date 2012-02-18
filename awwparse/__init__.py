# coding: utf-8
"""
    awwparse
    ~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE for details
"""
import sys
from itertools import count
from collections import OrderedDict

# _argparse is a patched argparse from cpython 2.7.2 that adds support for
# optional subparsers and hides subparsers with empty names properly from help
# (don't ask, no really you don't want to know)
import awwparse._argparse as argparse


class Namespace(dict):
    def __setattr__(self, name, value):
        if name.startswith("__") and name.endswith("__"):
            dict.__setattr__(self, name, value)
        else:
            self.set(name, value)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def set(self, name, value):
        self[name] = value

    def delete(self, name):
        del self[name]


class ConfigurableMeta(type):
    def __setattr__(self, name, attribute):
        if isinstance(attribute, Setting):
            del self._settings
        type.__setattr__(self, name, attribute)

    def __delattr__(self, name):
        del self._settings
        type.__delattr__(self, name)

    def __call__(self, *args, **kwargs):
        if not hasattr(self, "_settings"):
            self._settings = {}
            for attribute_name in dir(self):
                attribute = getattr(self, attribute_name)
                if isinstance(attribute, Setting):
                    self._settings[attribute_name] = attribute
        return type.__call__(self, *args, **kwargs)


class Configurable(object):
    __metaclass__ = ConfigurableMeta
    options = {}
    arguments = {}
    commands = {}

    #: The name of the application (default: sys.argv[0])
    prog = sys.argv[0]

    #: The usage string, will be auto-generated if None (default: None)
    usage = None

    #: A description of what the application does, which is displayed in the
    #: help. (default: None)
    description = None

    #: Text following the argument descriptions in the help. (default: None)
    epilog = None

    #: The formatter used for the help messages. (default:
    #: argparse.HelpFormatter)
    formatter_class = argparse.HelpFormatter

    #: Characters that prefix options. (default: "-")
    prefix_chars = "-"

    #: Characters that prefix files containing additional arguments. (default:
    #: None)
    fromfile_prefix_chars = None

    #: The default value for all arguments (default: None)
    argument_default = None

    #: Whether a -h/--help option should be added (default: True)
    add_help = True

    def __init__(self):
        self.options = self.options.copy()
        self.arguments = self.arguments.copy()
        self.commands = self.commands.copy()
        for name, setting in self._settings.iteritems():
            if isinstance(setting, Option):
                self.options[name] = setting
            elif isinstance(setting, Argument):
                self.arguments[name] = setting
            elif isinstance(setting, Command):
                self.commands[name] = setting

    def get_parser_kwargs(self):
        return {
            "prog": self.prog,
            "usage": self.usage,
            "description": self.description,
            "epilog": self.epilog,
            "formatter_class": self.formatter_class,
            "prefix_chars": self.prefix_chars,
            "fromfile_prefix_chars": self.fromfile_prefix_chars,
            "argument_default": self.argument_default,
            "add_help": self.add_help
        }

    def populate_with_options(self, parser):
        for option_name, option in self.options.iteritems():
            option.populate_parser(option_name, parser)

    def populate_with_arguments(self, parser):
        arguments = sorted(
            self.arguments.iteritems(),
            key=lambda i: i[1].creation_id
        )
        for argument_name, argument in arguments:
            argument.populate_parser(argument_name, parser)


class Application(Configurable):
    def __init__(self):
        Configurable.__init__(self)
        self._parser = argparse.ArgumentParser()
        self.subparsers = self._parser.add_subparsers(default="")
        self.parser = self.subparsers.add_parser(
            "", **self.get_parser_kwargs()
        )

        self.populate_with_options(self.parser)
        self.populate_with_arguments(self.parser)

        if self.commands:
            for command_name, command in self.commands.iteritems():
                command.populate_subparsers(command_name, self.subparsers)

    def __call__(self, argv=sys.argv):
        namespace = self._parser.parse_args(argv[1:], Namespace())
        run = namespace.pop("_run_command", None)
        if run is None:
            return self.run(**namespace)
        return run(self, **namespace)

    def run(self, **kwargs):
        raise NotImplementedError()


class Setting(object):
    pass


class Command(Configurable, Setting):
    @classmethod
    def calling(cls, with_name=None):
        def decorate(function):
            # Adds cls(function) to the commands class attribute of the
            # configurable, in whose scope the decorator was used. You are not
            # expected to understand this.
            commands = sys._getframe(1).f_locals.setdefault("commands", {})
            commands[with_name or function.__name__] = cls(function)
            return function
        return decorate

    def __init__(self, run):
        Configurable.__init__(self)
        self.run = run

    def populate_subparsers(self, name, subparsers):
        self.populate_parser(
            subparsers.add_parser(name, **self.get_parser_kwargs())
        )

    def populate_parser(self, parser):
        self.populate_with_options(parser)
        self.populate_with_arguments(parser)
        parser.set_defaults(_run_command=self.run)


class Action(argparse.Action):
    def __init__(self, *args, **kwargs):
        self.action = kwargs.pop("_action")
        self.validate = kwargs.pop("_validate")
        argparse.Action.__init__(self, *args, **kwargs)

class StoreAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        self.action(namespace, self.dest, self.validate(values))


class BooleanAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        self.action(namespace, self.dest)


class Parameter(Setting):
    action_type = StoreAction
    action = None
    default = argparse.SUPPRESS
    nargs = None
    help = None
    metavar = None

    def __init__(self,
                 action=None,
                 default=None,
                 nargs=None,
                 help=None,
                 metavar=None):
        if action is not None:
            self.action = action
        if default is not None:
            self.default = default
        if nargs is not None:
            self.nargs = nargs
        if help is not None:
            self.help = help
        if metavar is not None:
            self.metavar = metavar

    def as_add_argument_args(self, name):
        return (), {
            "action": self.action_type,
            "_action": self.action,
            "_validate": self.validate,
            "default": self.default,
            "nargs": self.nargs,
            "help": self.help,
            "metavar": self.metavar
        }

    def validate(self, value):
        raise NotImplementedError()

    def populate_parser(self, name, parser):
        args, kwargs = self.as_add_argument_args(name)
        parser.add_argument(*args, **kwargs)


class Option(Parameter):
    action_cls = None

    def __init__(self, short=None, long=None, **kwargs):
        Parameter.__init__(self, **kwargs)
        self.short = short
        self.long = long

    def as_add_argument_args(self, name):
        kwargs = Parameter.as_add_argument_args(self, name)[1]
        kwargs.update({"dest": name})
        return filter(None, [self.short, self.long]), kwargs


class Argument(Parameter):
    creation_counter = count()

    def __init__(self, *args, **kwargs):
        Parameter.__init__(self, *args, **kwargs)
        self.creation_id = self.creation_counter.next()

    def action(self, namespace, name, value):
        namespace.set(name, value)

    def as_add_argument_args(self, name):
        return (name, ), Parameter.as_add_argument_args(self, name)[1]


class Group(Setting):
    def __init__(self, settings):
        self.settings = OrderedDict(settings)

    def populate_parser(self, name, parser):
        raise NotImplementedError()


class CommandGroup(Group):
    def populate_parser(self, name, parser):
        subparsers = parser.add_subparsers(name)
        for command_name, command in self.settings.iteritems():
            command.populate_subparsers(command_name, subparsers)


class ParameterGroup(Group):
    def populate_parser(self, name, parser):
        group = parser.add_argument_group(name)
        for parameter_name, parameter in self.settings.iteritems():
            group.add_argument(*parameter.as_add_argument_args(parameter_name))
