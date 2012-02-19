# coding: utf-8
"""
    awwparse.utils
    ~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst for details
"""
import sys
from pkgutil import iter_modules


def import_string(import_name, silent=False):
    """
    Imports an object based on a string. An import path can be specified either
    in dotted notation (``xml.sax.saxutils.escape``).

    If `silent` is `True` the return value will be `None` if the import fails.

    :param import_name: the dotted name for the object to import.
    :param silent: if set to `True` import errors are ignored and
                   `None` is returned instead.
    :return: imported object
    """
    # This code has been taken from Werkzeug, see LICENSE.rst for more details
    try:
        if "." in import_name:
            module, obj = import_name.rsplit(".", 1)
        else:
            return __import__(import_name)
        try:
            return getattr(__import__(module, None, None, [obj]), obj)
        except (ImportError, AttributeError):
            modname = module + "." + obj
            __import__(modname)
            return sys.modules[modname]
    except ImportError, e:
        if not silent:
            raise ImportStringError(import_name, e), None, sys.exc_info()[2]


class ImportStringError(ImportError):
    """
    Provides information about a failed :func:`import_string` attempt.
    """
    # This code has been taken from Werkzeug, see LICENSE.rst for more details
    def __init__(self, import_name, exception):
        self.import_name = import_name
        self.exception = exception

        msg = (
            "import_string() failed for %r. Possible reasons are:\n\n"
            "- missing __init__.py in a package;\n"
            "- package or module path not included in sys.path;\n"
            "- duplicated package or module name taking precedence in "
            "sys.path;\n"
            "- missing module, class, function or variable;\n\n"
            "Debugged import:\n\n%s\n\n"
            "Original exception:\n\n%s: %s"
        )

        name = ""
        tracked = []
        for part in import_name.split("."):
            name += (name and ".") + part
            imported = import_string(name, silent=True)
            if imported:
                tracked.append((name, getattr(imported, "__file__", None)))
            else:
                track = ["- %r found in %r." % (n, i) for n, i in tracked]
                track.append("- %r not found." % name)
                msg = msg % (
                    import_name, "\n".join(track),
                    exception.__class__.__name__,
                    str(exception)
                )
                break
        ImportError.__init__(self, msg)

    def __repr__(self):
        return "<%s(%r, %r)>" % (
            self.__class__.__name__, self.import_name, self.exception
        )


def find_modules(import_name, include_packages=False, recursive=False):
    """
    Find all the modules below a package.

    Packages are not returned unless `include_packages` is `True`. This can
    also recursively list modules but in that case it will import all the
    packages to get the correct load path of that module.

    :param import_name: the dotted name for the package to find child modules.
    :param include_packages: set to `True` if packages should be returned, too.
    :param recursive: set to `True` if recursion should happen.
    :return: generator
    """
    # This code has been taken from Werkzeug, see LICENSE.rst for more details
    module = import_string(import_name)
    path = getattr(module, "__path__", None)
    if path is None:
        raise ValueError("%r is not a package" % import_name)
    basename = module.__name__ + "."
    for _, modname, ispkg in iter_modules(path):
        modname = basename + modname
        if ispkg:
            if include_packages:
                yield modname
            if recursive:
                for item in find_modules(modname, include_packages, True):
                    yield item
        else:
            yield modname
