# coding: utf-8
"""
    awwparse.positionals
    ~~~~~~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import sys
import locale
import codecs
import decimal
from abc import ABCMeta, abstractmethod
try:
    from urllib.parse import urlparse
except:
    from urlparse import urlparse

import six
from six import u

try:
    import requests
except ImportError:
    requests = None

from awwparse.utils import create_repr
from awwparse.exceptions import (
    UserTypeError, ArgumentMissing, EndOptionParsing
)


def parse_positional_signature(positionals, require_metavar=False, _root=True):
    result = []
    if not _root:
        positionals[0].optional = True
    for positional in positionals:
        if isinstance(positional, Positional):
            if require_metavar and positional.metavar is None:
                raise ValueError("metavar not set on: {0!r}".format(positional))
            result.append(positional)
        else:
            result.extend(parse_positional_signature(
                positional, require_metavar=require_metavar, _root=False
            ))
    return result


class Positional(object):
    def __init__(self, metavar=None, optional=False, remaining=False,
                 help=None):
        self.metavar = metavar
        self.optional = optional
        self.remaining = remaining
        self.help = help

    def setdefault_metavar(self, metavar):
        if self.metavar is None:
            self.metavar = metavar

    def copy_args(self):
        return {
            "metavar": self.metavar,
            "optional": self.optional,
            "remaining": self.remaining,
            "help": self.help
        }

    def copy(self):
        return self.__class__(**self.copy_args())

    @property
    def usage(self):
        if self.remaining:
            return u("[{0} ...]").format(self.metavar)
        return self.metavar

    def parse(self, command, arguments):
        raise NotImplementedError()

    def parse_as_positional(self, command, result, arguments):
        parsed = self.parse(command, arguments)
        if self.remaining:
            result.extend(parsed)
        else:
            result.append(parsed)
        return result

    def get_next_argument(self, command, arguments):
        try:
            argument = next(arguments)
        except StopIteration:
            raise ArgumentMissing(self.metavar)
        else:
            if command.is_option(argument):
                raise ArgumentMissing(argument)
            return argument

    def __repr__(self):
        return create_repr(self.__class__.__name__, kwargs=self.copy_args())


class EncodingPositional(Positional):
    error_method = "replace"

    def get_encoding(self, command):
        return getattr(command, "stdin.encoding", locale.getpreferredencoding())


class Bytes(EncodingPositional):
    """
    Represents a binary argument.
    """
    def encode(self, string, encoding):
        if isinstance(string, six.binary_type):
            return string
        try:
            return string.encode(encoding, self.error_method)
        except UnicodeEncodeError:
            raise UserTypeError(
                u("failed to decode {string!r} with {encoding!r}").format(
                    string=string,
                    encoding=encoding
                )
            )

    def parse(self, command, arguments):
        encoding = self.get_encoding(command)
        if self.remaining:
            return [self.encode(string, encoding) for string in arguments]
        try:
            return self.encode(
                self.get_next_argument(command, arguments),
                encoding
            )
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise


class String(EncodingPositional):
    """
    Represents a string argument.
    """
    def decode(self, bytes, encoding):
        if isinstance(bytes, six.text_type):
            return bytes
        try:
            return bytes.decode(encoding, self.error_method)
        except UnicodeDecodeError:
            raise UserTypeError(
                u("failed to decode {bytes!r} with {encoding!r}").format(
                    bytes=bytes,
                    encoding=encoding
                )
            )

    def parse(self, command, arguments):
        encoding = self.get_encoding(command)
        if self.remaining:
            return [self.decode(bytes, encoding) for bytes in arguments]
        try:
            return self.decode(
                self.get_next_argument(command, arguments),
                encoding
            )
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise


class NativeString(Positional):
    """
    Represents a "native" string argument.
    """
    def parse(self, command, arguments):
        if self.remaining:
            return list(arguments)
        try:
            return self.get_next_argument(command, arguments)
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise


class ConverterBase(Positional):
    type = None
    type_conversion_exception = ValueError
    error_message = u("")

    def convert(self, argument):
        try:
            return self.type(argument)
        except self.type_conversion_exception:
            raise UserTypeError(self.error_message.format(argument=argument))

    def parse(self, command, arguments):
        if self.remaining:
            return list(map(self.convert, arguments))
        try:
            argument = self.get_next_argument(command, arguments)
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise
        else:
            return self.convert(argument)


class Integer(ConverterBase):
    """
    Represents an integer argument.
    """
    type = int
    error_message = u("{argument!r} is not an integer")


class Float(ConverterBase):
    """
    Represents a float argument.
    """
    type = float
    error_message = u("{argument!r} is not a float")


class Decimal(ConverterBase):
    """
    Like :class:`Float` but uses :class:`decimal.Decimal` for higher precision.
    """
    type = decimal.Decimal
    type_conversion_exception = decimal.InvalidOperation
    error_message = u("{argument!r} is not a decimal")


class Complex(ConverterBase):
    """
    Represents a complex number argument.
    """
    type = complex
    error_message = u("{argument!r} is not a complex number")


class Any(ConverterBase):
    """
    Represents an argument of one of the given `positionals`.

    Raises a :exc:`UserTypeError` with the given `error_message` if no
    positional successfully parses.
    """
    def __init__(self, positionals, error_message, **kwargs):
        ConverterBase.__init__(self, **kwargs)
        self.positionals = positionals
        self.error_message = error_message

    def copy_args(self):
        args = ConverterBase.copy_args(self)
        args.update({
            "positionals": [
                positional.copy() for positional in self.positionals
            ],
            "error_message": self.error_message
        })
        return args

    def convert(self, string):
        for positional in self.positionals:
            try:
                return positional.convert(string)
            except UserTypeError:
                pass
        raise UserTypeError(self.error_message.format(argument=string))

    def __repr__(self):
        return create_repr(
            self.__class__.__name__,
            [self.positionals, self.error_message],
            ConverterBase.copy_args(self)
        )


class Number(Any):
    """
    Represents an integer, a float or a complex number.
    """
    def __init__(self, use_decimal=False, **kwargs):
        Any.__init__(
            self,
            [Integer(), (Decimal if use_decimal else Float)(), Complex()],
            u("{argument!r} is not a number"),
            **kwargs
        )
        self.use_decimal = use_decimal

    def copy_args(self):
        args = Any.copy_args(self)
        args.update({"use_decimal": self.use_decimal})
        del args["positionals"]
        del args["error_message"]
        return args

    def __repr__(self):
        return create_repr(self.__class__.__name__, kwargs=self.copy_args())


class Boolean(Positional):
    """
    Represents a boolean.
    """
    def __init__(self, store=True, **kwargs):
        Positional.__init__(self, **kwargs)
        self.store = store

    @property
    def usage(self):
        return u("")

    def copy_args(self):
        args = Positional.copy_args(self)
        args.update({"store": self.store})
        return args

    def parse(self, command, arguments):
        return self.store

    def __repr__(self):
        return create_repr(self.__class__.__name__, kwargs=self.copy_args())


class Choice(Positional):
    """
    Represents a choice between `choices` where the choice is something of
    `argument`.
    """
    def __init__(self, argument, choices, **kwargs):
        Positional.__init__(self, **kwargs)
        self.argument = argument
        self.choices = choices

    def copy_args(self):
        args = Positional.copy_args(self)
        args.update({
            "argument": self.argument.copy(),
            "choices": self.choices
        })
        return args

    def parse_single(self, command, arguments):
        parsed = self.argument.parse(command, arguments)
        if parsed not in self.choices:
            raise UserTypeError(
                u("{argument!r} not one of {choices}").format(
                    argument=parsed,
                    choices=", ".join(map(repr, self.choices))
                )
            )
        return parsed

    def parse(self, command, arguments):
        if self.remaining:
            result = []
            while arguments:
                result.append(self.parse_single(command, arguments))
            return result
        try:
            return self.parse_single(command, arguments)
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise

    def __repr__(self):
        return create_repr(
            self.__class__.__name__,
            [self.argument, self.choices],
            Positional.copy_args(self)
        )


class Mapping(Positional):
    """
    Like :class:`Choice` but uses a mapping and returns the value.
    """
    def __init__(self, positional, mapping, **kwargs):
        Positional.__init__(self, **kwargs)
        self.positional = positional
        self.mapping = mapping

    def copy_args(self):
        args = Positional.copy_args(self)
        args.update({
            "positional": self.positional.copy(),
            "mapping": self.mapping.copy()
        })
        return args

    def parse_single(self, command, arguments):
        parsed = self.positional.parse(command, arguments)
        try:
            return self.mapping[parsed]
        except KeyError:
            raise UserTypeError(u("{argument!r} not on of {choices}").format(
                argument=repr(parsed),
                choices=u(", ").join(map(repr, self.mapping))
            ))

    def parse(self, command, arguments):
        if self.remaining:
            result = []
            while arguments:
                result.append(self.parse_single(command, arguments))
            return result
        try:
            return self.parse_single(command, arguments)
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise

    def __repr__(self):
        return create_repr(
            self.__class__.__name__,
            [self.positional, self.mapping],
            {
                "metavar": self.metavar,
                "optional": self.optional,
                "remaining": self.remaining,
                "help": self.help
            }
        )


class LocalResource(Positional):
    """
    Represents a file or standard stream (`sys.std{in,out}`) and returns an
    :class:`Opener` object.

    You can define which argument opens a standard stream with
    `std_stream_argument`, whether standard streams should be used at all with
    `allow_std_streams` and whether they should be closed with
    `close_std_stream`.

    If Python 2.x is used and `encoding` is not ``None`` :func:`codecs.open()`
    will be used instead of :func:`open()`.

    Standard streams will be wrapped in a :class:`codecs.StreamReaderWriter` if
    Python 2.x is used and `encoding` is not ``None`` or Python 3.x is used but
    the encoding of the stream is unknown
    (``getattr(stream, "encoding", None) is None``) and `encoding` is not
    ``None``.

    If standard streams are allowed (the default), `mode` has to be either
    `r` or `w` which will open `sys.stdin` and `sys.stdout` respectively,
    otherwise a :exc:`ValueError` will be raised.

    For the remaining arguments refer to :func:`open()`,
    `open()`_ and :func:`codecs.open()`.

    .. _open(): http://docs.python.org/dev/library/functions.html#open
    """
    def __init__(self, mode="r", buffering=-1, encoding=None, errors=None,
                 newline=None, opener=None, std_stream_argument="-",
                 allow_std_streams=True, close_std_stream=False, **kwargs):
        Positional.__init__(self, **kwargs)
        if allow_std_streams and mode not in set(["r", "w"]):
            raise ValueError(
                "invalid mode for standard stream: {0!r}".format(mode)
            )
        self.mode = mode
        self.buffering = buffering
        self.encoding = encoding
        self.errors = errors
        self.newline = newline
        self.opener = opener
        self.std_stream_argument = std_stream_argument
        self.allow_std_streams = allow_std_streams
        self.close_std_stream = close_std_stream

    def copy_args(self):
        args = Positional.copy_args(self)
        args.update({
            "mode": self.mode,
            "buffering": self.buffering,
            "encoding": self.encoding,
            "errors": self.errors,
            "newline": self.newline,
            "opener": self.opener,
            "std_stream_argument": self.std_stream_argument,
            "allow_std_streams": self.allow_std_streams,
            "close_std_stream": self.close_std_stream
        })
        return args

    def parse(self, command, arguments):
        if self.remaining:
            result = []
            while arguments:
                result.append(self.parse_single(command, arguments))
            return result
        try:
            return self.parse_single(command, arguments)
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise

    def parse_single(self, command, arguments):
        argument = self.get_next_argument(command, arguments)
        return LocalResourceOpener(
            command,
            argument,
            mode=self.mode,
            buffering=self.buffering,
            encoding=self.encoding,
            errors=self.errors,
            newline=self.newline,
            opener=self.opener,
            std_stream_resource=self.std_stream_argument,
            allow_std_streams=self.allow_std_streams,
            close_std_stream=self.close_std_stream
        )

    def __repr__(self):
        return create_repr(self.__class__.__name__, [], self.copy_args())


class Resource(Positional):
    """
    Represents a resource and returns an :class:`Opener` object.

    Schemes:
     - `""` - No scheme given: file or standard stream
     - `"file"`
     - `"http"`
    """
    def __init__(self, schemes=None, opener_arguments=None, **kwargs):
        Positional.__init__(self, **kwargs)
        self.schemes = schemes
        self.opener_arguments = opener_arguments

    def copy_args(self):
        args = Positional.copy_args(self)
        if self.schemes is None:
            schemes = self.schemes
        else:
            schemes = self.schemes.copy()
        if self.opener_arguments is None:
            opener_arguments = self.opener_arguments
        else:
            opener_arguments = dict(
                (scheme, (args, kwargs.copy()))
                for (scheme, (args, kwargs)) in self.opener_arguments.items()
        )
        args.update({
            "schemes": schemes,
            "opener_arguments": opener_arguments
        })
        return args

    def parse(self, command, arguments):
        if self.remaining:
            result = []
            while arguments:
                result.append(self.parse_single(command, arguments))
            return result
        try:
            return self.parse_single(command, arguments)
        except ArgumentMissing:
            if self.optional:
                raise EndOptionParsing()
            raise

    def parse_single(self, command, arguments):
        argument = self.get_next_argument(command, arguments)
        return SchemeDispatchingOpener(
            command, argument, self.schemes, self.opener_arguments
        )


class Opener(object):
    """
    A base class for context managers that acquire and release resources.
    """
    __metaclass__ = ABCMeta

    def __init__(self, command):
        self.command = command
        self.resource = None

    @abstractmethod
    def acquire_resource(self):
        """
        Acquires and returns the resource.

        Must be implemented by subclasses.
        """
        raise NotImplementedError()

    @abstractmethod
    def release_resource(self, resource):
        """
        Releases the resource.

        Must be implemented by subclasses.
        """
        raise NotImplementedError()

    def __enter__(self):
        self.resource = self.acquire_resource()
        return self.resource

    def __exit__(self, exc_type, exc_value, traceback):
        self.release_resource(self.resource)


class FileOpener(Opener):
    def __init__(self, command, path, mode="r", buffering=-1, encoding=None,
                 errors=None, newline=None, opener=None):
        Opener.__init__(self, command)
        components = urlparse(path)
        if components.scheme == "file":
            self.path = components.netloc + components.path
        else:
            self.path = path
        self.mode = mode
        self.buffering = buffering
        self.encoding = encoding
        self.errors = errors
        self.newline = newline
        self.opener = opener

    def acquire_resource(self):
        if six.PY3:
            kwargs = {}
            if sys.version_info >= (3, 3):
                kwargs["opener"] = self.opener
            return open(
                self.path,
                mode=self.mode,
                buffering=self.buffering,
                encoding=self.encoding,
                errors=self.errors,
                newline=self.newline,
                **kwargs
            )
        elif self.encoding is None:
            return open(
                self.path,
                mode=self.mode,
                buffering=self.buffering
            )
        else:
            return codecs.open(
                self.path,
                mode=self.mode,
                buffering=self.buffering,
                encoding=self.encoding,
                errors=self.errors
            )

    def release_resource(self, file):
        file.close()

    def __repr__(self):
        return create_repr(
            self.__class__.__name__,
            [self.path],
            {
                "mode": self.mode,
                "buffering": self.buffering,
                "encoding": self.encoding,
                "errors": self.errors,
                "newline": self.newline,
                "opener": self.opener
            }
        )


class StandardStreamOpener(Opener):
    def __init__(self, command, stream, should_close=False, encoding=None,
                 errors=None):
        Opener.__init__(self, command)
        self.stream = stream
        self.should_close = should_close
        self.encoding = encoding
        self.errors = errors

    def acquire_resource(self):
        if (six.PY3 and
            getattr(self.stream, "encoding", None) is not None and
            self.encoding is not None or
            self.encoding is None):
            return self.stream
        else:
            codec_info = codecs.lookup(self.encoding)
            return codecs.StreamReaderWriter(
                self.stream,
                codec_info.streamreader,
                codec_info.streamwriter,
                self.errors
            )

    def release_resource(self, file):
        if self.should_close:
            file.close()

    def __repr__(self):
        return create_repr(
            self.__class__.__name__,
            [self.stream],
            {
                "should_close": self.should_close,
                "encoding": self.encoding,
                "errors": self.errors
            }
        )


class LocalResourceOpener(Opener):
    std_stream_modes = frozenset(["r", "w"])

    def __init__(self, command, url, mode="r", buffering=-1, encoding=None,
                 errors=None, newline=None, opener=None,
                 std_stream_resource="-", allow_std_streams=True,
                 close_std_stream=False):
        Opener.__init__(self, command)
        self.std_stream_resource = std_stream_resource
        self.allow_std_streams = allow_std_streams
        self.close_std_stream = close_std_stream
        self.url = url
        self.mode = mode
        self.buffering = buffering
        self.encoding = encoding
        self.errors = errors
        self.newline = newline
        self.opener = opener
        self._opener = None

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, new_mode):
        if self.allow_std_streams and new_mode not in self.std_stream_modes:
            raise ValueError(
                "invalid mode for standard stream: {0!r}".format(new_mode)
            )
        self._mode = new_mode

    def acquire_resource(self):
        if self.allow_std_streams and self.url == self.std_stream_resource:
            if self.mode == "r":
                stream = self.command.stdin
            else:
                stream = self.command.stdout
            self._opener = StandardStreamOpener(
                self.command,
                stream,
                should_close=self.close_std_stream,
                encoding=self.encoding,
                errors=self.errors
            )
        else:
            self._opener = FileOpener(
                self.command,
                self.url,
                mode=self.mode,
                buffering=self.buffering,
                encoding=self.encoding,
                errors=self.errors,
                newline=self.newline,
                opener=self.opener
            )
        return self._opener.acquire_resource()

    def release_resource(self, resource):
        if self._opener is None:
            raise RuntimeError(
                "called release_resource before acquire_resource"
            )
        self._opener.release_resource(resource)


class HTTPRequestOpener(Opener):
    def __init__(self, command, url, **kwargs):
        Opener.__init__(self, command)
        if requests is None:
            raise RuntimeError("requires 'requests' to be installed")
        self.url = url
        self.kwargs = kwargs
        headers = self.kwargs.setdefault("headers", {})
        headers.setdefault("User-Agent", "Awwparse/0.1-dev")

    def acquire_resource(self):
        return requests.get(self.url, **self.kwargs)

    def release_resource(self, response):
        # response objects cannot be closed
        pass


class SchemeDispatchingOpener(Opener):
    # TODO: Add an FTPOpener. If we were using urllib(2), we would get FTP
    #       support for free but apparently requests doesn't implement the FTP
    #       scheme. The standard library has ftplib for dealing with FTP but
    #       the abstraction is quite leaky and requires knowledge of the
    #       protocol I don't have. urllib(2) uses some kind of wrapper around
    #       FTPlib to deal with this problem but it seems to do a lot more than
    #       is actually necessary. The best approach is probably to research
    #       the FTP protocol and implement a wrapper by stripping down the
    #       urllib(2) one to what is really needed.
    default_schemes = {
        "": LocalResourceOpener,
        "file": FileOpener,
        "http": HTTPRequestOpener
    }

    def __init__(self, command, resource, schemes=None, opener_arguments=None):
        Opener.__init__(self, command)
        if schemes is None:
            self.schemes = self.default_schemes.copy()
        else:
            self.schemes = schemes
        scheme = urlparse(resource).scheme
        opener_arguments = {} if opener_arguments is None else opener_arguments
        args, kwargs = opener_arguments.get(scheme, ((), {}))
        self.opener = self.schemes[scheme](
            self.command, resource, *args, **kwargs
        )

    def acquire_resource(self):
        return self.opener.acquire_resource()

    def release_resource(self, resource):
        self.opener.release_resource(resource)
