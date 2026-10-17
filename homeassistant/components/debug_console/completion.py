"""Completion and signature hints for code typed in the Debug console.

All of this runs while typing, so it never runs user code: no properties,
descriptors, __getattr__, or __dir__, and no importing modules.
"""

from abc import ABCMeta
import builtins
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from importlib.machinery import all_suffixes
import inspect
from itertools import pairwise
import keyword
import os
import re
import sys
import types
from typing import Any

from homeassistant.core import HomeAssistant

from .inspection import (
    class_dict,
    class_mro,
    has_type,
    instance_dict,
    is_class,
    is_descriptor,
    preview,
    static_attribute,
    static_lookup,
    with_string_names,
)

MAX_COMPLETIONS = 200

# Completion contexts, matched against the line up to the cursor.
_IMPORT_MODULE = re.compile(
    r"^\s*import\s+(?:[\w.]+(?:\s+as\s+\w+)?\s*,\s*)*(?P<module>[\w.]*)$"
)
_FROM_MODULE = re.compile(r"^\s*from\s+(?P<module>[\w.]*)$")
_FROM_IMPORT_NAME = re.compile(
    r"^\s*from\s+(?P<module>[\w.]+)\s+import\s+\(?\s*"
    r"(?:\w+(?:\s+as\s+\w+)?\s*,\s*)*(?P<name>\w*)$"
)
_TOKEN = re.compile(r"(?P<token>[\w.]+)$")
_CALLEE = re.compile(r"(?P<callee>[A-Za-z_][\w.]*)\s*$")
_KEYWORD_ARGUMENT = re.compile(r"\s*(?P<name>\w+)\s*=(?!=)")

_MISSING = object()

# Default values shown in signatures; others could bring their own __repr__.
_SAFE_DEFAULT_TYPES = (type(None), bool, int, float, complex, str, bytes)

# Callables whose signature inspect can read without running user code.
_SIGNATURE_TYPES = (
    types.FunctionType,
    types.BuiltinFunctionType,
    types.MethodDescriptorType,
    types.WrapperDescriptorType,
    types.MethodWrapperType,
    types.ClassMethodDescriptorType,
)

# Constructors of classes written in C, whose signature inspect reads safely.
_BUILTIN_CONSTRUCTOR_TYPES = (
    types.BuiltinFunctionType,
    types.WrapperDescriptorType,
    types.MethodDescriptorType,
)

# Endings of files that are modules, longest first, as ".so" ends others too.
_MODULE_SUFFIXES = sorted(all_suffixes(), key=len, reverse=True)

# Flag of classes written in Python, which can have a __text_signature__ from
# their docstring.
_HEAP_TYPE = 1 << 9

# Metaclasses of classes whose signature inspect can read safely.
_STANDARD_METACLASSES = (type, ABCMeta)

# Descriptors that only bind functions, so binding them runs no user code.
_SAFE_DESCRIPTORS = (
    types.FunctionType,
    staticmethod,
    classmethod,
    types.MethodDescriptorType,
    types.ClassMethodDescriptorType,
    types.WrapperDescriptorType,
)


@dataclass(slots=True, frozen=True)
class _OpenCall:
    """A call that is still being typed."""

    callee: str
    # The text of each argument so far; the last one is being typed.
    arguments: list[str]


async def async_complete(
    hass: HomeAssistant, namespace: dict[str, Any], code: str
) -> dict[str, Any]:
    """Return completions for the code being typed, up to the cursor.

    The token is the part of the line being completed, so the frontend knows
    what the matches replace.
    """
    line = code.rpartition("\n")[2]

    # Finding modules scans the disk, so not in the event loop.
    if match := _IMPORT_MODULE.match(line) or _FROM_MODULE.match(line):
        token = match["module"]
        matches = await hass.async_add_executor_job(_complete_module, token)
    elif match := _FROM_IMPORT_NAME.match(line):
        token = match["name"]
        matches = await hass.async_add_executor_job(
            _complete_module_attribute, match["module"], token
        )
    else:
        token = match["token"] if (match := _TOKEN.search(line)) else ""
        matches = [
            *_complete_keyword_arguments(namespace, code, token),
            *_complete_namespace(namespace, token),
        ]

    return {"token": token, "matches": matches[:MAX_COMPLETIONS]}


def signature_hint(namespace: dict[str, Any], code: str) -> dict[str, Any] | None:
    """Return the signature of the call being typed, if any."""
    if (call := _find_open_call(code)) is None or (
        signature := _signature(namespace, call.callee)
    ) is None:
        return None

    parameters = list(signature.parameters.values())
    active = _active_parameter(parameters, call.arguments)
    doc = _doc(_resolve(namespace, call.callee))

    return {
        "name": call.callee.rpartition(".")[2],
        "parameters": [_format_parameter(parameter) for parameter in parameters],
        "active": None if active is None else parameters.index(active),
        "returns": _annotation(signature.return_annotation),
        "doc": doc.partition("\n")[0],
    }


def _find_open_call(code: str) -> _OpenCall | None:
    """Return the innermost call that is still open at the end of the code."""
    # Each open bracket, with the positions of the commas directly inside it.
    brackets: list[tuple[int, list[int]]] = []
    quote: str | None = None
    index = 0

    while index < len(code):
        char = code[index]
        if quote is not None:
            if char == "\\":
                index += 1
            elif code.startswith(quote, index):
                index += len(quote) - 1
                quote = None
        elif char in "\"'":
            three = code[index : index + 3]
            quote = three if three in ('"""', "'''") else char
            index += len(quote) - 1
        elif char == "#":
            if (index := code.find("\n", index)) == -1:
                break
        elif char in "([{":
            brackets.append((index, []))
        elif char in ")]}" and brackets:
            brackets.pop()
        elif char == "," and brackets:
            brackets[-1][1].append(index)

        index += 1

    if not brackets or code[(start := brackets[-1][0])] != "(":
        return None

    if (callee := _CALLEE.search(code, 0, start)) is None:
        return None

    bounds = [start, *brackets[-1][1], len(code)]
    return _OpenCall(
        callee=callee["callee"],
        arguments=[code[begin + 1 : end] for begin, end in pairwise(bounds)],
    )


def _resolve(namespace: dict[str, Any], expression: str) -> Any:
    """Resolve a dotted name without running any code, or return _MISSING."""
    first, *attributes = expression.split(".")

    for names in _global_names(namespace):
        if first in names:
            value = names[first]
            break
    else:
        return _MISSING

    # Without getattr(), as properties, descriptors, and __getattr__ run code.
    for attribute in attributes:
        if (found := static_lookup(value, attribute)) is None:
            return _MISSING

        static = found.attribute
        if found.owner is None or not is_descriptor(static):
            # Plain values, including those in the __dict__ of an instance.
            value = static
        elif has_type(static, _SAFE_DESCRIPTORS):
            # Through its type, as a function can store a __get__ of its own.
            value = type(static).__get__(static, found.instance, found.owner)  # pylint: disable=unnecessary-dunder-call
        elif type(static) is types.MemberDescriptorType and found.instance is not None:
            try:
                value = type(static).__get__(static, found.instance, found.owner)  # pylint: disable=unnecessary-dunder-call
            except AttributeError:
                # A slot that is not set yet.
                return _MISSING
        else:
            return _MISSING

    return value


def _signature(namespace: dict[str, Any], callee: str) -> inspect.Signature | None:
    """Return the signature of a callable, or None if it has none."""
    if (target := _resolve(namespace, callee)) is _MISSING or not _has_safe_signature(
        target
    ):
        return None

    try:
        return _read_signature(_unwrap(target))
    except TypeError, ValueError:
        return None


def _read_signature(target: Any) -> inspect.Signature:
    """Read the signature of a callable that passed _has_safe_signature.

    Not inspect.signature for functions and classes: it evaluates annotations,
    even as strings, and the defaults of a __text_signature__. Both can run any
    code. Their signature comes from a copy of the function without those.
    """
    if type(explicit := static_attribute(target, "__signature__")) is (
        inspect.Signature
    ):
        return explicit

    if type(target) is types.MethodType:
        return _without_first_parameter(_read_signature(target.__func__))

    if type(target) is types.FunctionType:
        return inspect.signature(_without_annotations(target), follow_wrapped=False)

    if is_class(target):
        # Like inspect: the first __new__ or __init__ written in Python.
        for cls in class_mro(target):
            attributes = class_dict(cls)
            for name in ("__new__", "__init__"):
                constructor = attributes.get(name)
                if (
                    type(constructor) is staticmethod
                    or type(constructor) is classmethod
                ):
                    constructor = constructor.__func__

                if type(constructor) is types.FunctionType:
                    return _without_first_parameter(_read_signature(constructor))

        # Otherwise, that of the first class written in C, which has no
        # annotations, nor a __text_signature__ from code of the user.
        target = next(cls for cls in class_mro(target) if not _is_heap_type(cls))

    # Callables written in C.
    return inspect.signature(target, follow_wrapped=False)


def _doc(value: Any) -> str:
    """Return the docstring of a callable that passed _has_safe_signature.

    Not inspect.getdoc, which also searches classes when the doc is missing.
    A bound method reads it from what it binds, and a class runs a descriptor
    stored as its __doc__, so both read it from where it is stored.
    """
    while type(value) is types.MethodType:
        value = value.__func__

    doc = class_dict(value).get("__doc__") if is_class(value) else value.__doc__
    return inspect.cleandoc(doc) if type(doc) is str else ""


def _without_annotations(function: types.FunctionType) -> types.FunctionType:
    """Return a copy of a function, with only the annotations stored as text.

    Others are evaluated on request, by its __annotate__, which runs code. Its
    defaults are copied too: code can set subclasses of tuple and dict, with
    methods of their own. The copies read the storage underneath.
    """
    defaults = function.__defaults__
    if defaults is not None:
        defaults = tuple.__getitem__(defaults, slice(None))

    keyword_defaults = function.__kwdefaults__
    if keyword_defaults is not None:
        keyword_defaults = with_string_names(dict.items(keyword_defaults))

    copy = types.FunctionType(
        function.__code__,
        function.__globals__,
        function.__name__,
        defaults,
        function.__closure__,
        keyword_defaults,
    )

    if function.__annotate__ is None:
        copy.__annotations__ = {
            name: annotation
            for name, annotation in dict.items(function.__annotations__)
            if type(name) is str and type(annotation) is str
        }

    return copy


def _without_first_parameter(signature: inspect.Signature) -> inspect.Signature:
    """Return a signature without the parameter that binding fills in."""
    parameters = list(signature.parameters.values())
    if parameters and parameters[0].kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ):
        parameters = parameters[1:]

    return signature.replace(parameters=parameters)


def _is_heap_type(cls: type) -> bool:
    """Return if a class is written in Python, not in C."""
    return bool(cls.__flags__ & _HEAP_TYPE)


def _unwrap(target: Any) -> Any:
    """Return what a decorated function wraps, as long as that is safe to read.

    Like inspect.unwrap, which leaves classes alone too, but reads __wrapped__
    with getattr(). For a bound method, that runs code of what it binds.
    """
    # A bound method keeps __wrapped__ on its function, and binding what that
    # wraps keeps the first argument out of the signature.
    if type(target) is types.MethodType:
        return types.MethodType(_unwrap(target.__func__), target.__self__)

    seen = {id(target)}
    while (
        not is_class(target)
        # A wrapper can give its own signature, which inspect then uses too.
        and static_attribute(target, "__signature__", _MISSING) is _MISSING
        and (wrapped := static_attribute(target, "__wrapped__", _MISSING))
        is not _MISSING
        and _has_safe_signature(wrapped)
    ):
        # A wrapper that wraps itself, directly or not, would loop forever.
        if id(wrapped) in seen:
            break

        seen.add(id(wrapped))
        target = wrapped

    return target


def _has_safe_signature(value: Any) -> bool:
    """Return if inspect can read the signature without running user code.

    For other callable objects, and classes with a metaclass of their own,
    inspect reads attributes like __signature__, which can be properties.
    """
    if is_class(value):
        return has_type(value, _STANDARD_METACLASSES) and all(
            _has_safe_constructors(class_dict(cls)) for cls in class_mro(value)
        )

    # A method binds any callable, and inspect reads the signature of that.
    if type(value) is types.MethodType:
        return _has_safe_signature(value.__func__)

    if type(value) is types.FunctionType:
        return _has_plain_signature_attributes(instance_dict(value) or {})

    return has_type(value, _SIGNATURE_TYPES)


def _has_plain_signature_attributes(attributes: Mapping[str, Any]) -> bool:
    """Return if inspect can read the signature attributes of a callable safely.

    It reads them with getattr(), which runs a descriptor stored there, and
    checks if __text_signature__ is true, which can run its __bool__.
    """
    return (
        _is_plain_signature(attributes.get("__signature__"))
        and has_type(attributes.get("__text_signature__"), (type(None), str))
        and "__partialmethod__" not in attributes
    )


def _is_plain_signature(signature: Any) -> bool:
    """Return if an explicit signature holds nothing that can run code.

    Its parameters can be subclasses, with properties of their own.
    """
    if signature is None:
        return True

    return type(signature) is inspect.Signature and all(
        type(parameter) is inspect.Parameter and type(parameter.name) is str
        for parameter in signature.parameters.values()
    )


def _has_safe_constructors(attributes: Mapping[str, Any]) -> bool:
    """Return if inspect can read the signature of a class defining these.

    It reads the class like a function, and the __new__ and __init__ it uses
    for the signature.
    """
    if not _has_plain_signature_attributes(attributes):
        return False

    for name in ("__new__", "__init__"):
        if (constructor := attributes.get(name)) is None:
            continue

        if has_type(constructor, (staticmethod, classmethod)):
            constructor = constructor.__func__

        if has_type(constructor, _BUILTIN_CONSTRUCTOR_TYPES):
            continue

        if not _is_plain_function(constructor):
            return False

    return True


def _is_plain_function(value: Any) -> bool:
    """Return if a value is a function, with nothing unusual to read."""
    return type(value) is types.FunctionType and _has_plain_signature_attributes(
        instance_dict(value) or {}
    )


def _format_parameter(parameter: inspect.Parameter) -> str:
    """Format a parameter like Python, without quoting its string annotation."""
    text = parameter.name
    if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
        text = f"*{text}"
    elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
        text = f"**{text}"

    annotation = _annotation(parameter.annotation)
    if annotation is not None:
        text = f"{text}: {annotation}"

    if parameter.default is not inspect.Parameter.empty:
        separator = " = " if annotation is not None else "="
        text = f"{text}{separator}{_format_default(parameter.default)}"

    return text


def _annotation(annotation: Any) -> str | None:
    """Return an annotation, if it is a string.

    Annotations are read as strings, except those of an explicit __signature__,
    which can be any object; formatting that could run its code.
    """
    return annotation if type(annotation) is str else None


def _format_default(value: Any) -> str:
    """Format a default value, without running a __repr__ of the user."""
    if has_type(value, _SAFE_DEFAULT_TYPES):
        return preview(value)

    return "…"


def _active_parameter(
    parameters: list[inspect.Parameter], arguments: list[str]
) -> inspect.Parameter | None:
    """Return the parameter the argument being typed goes to."""
    if keyword_argument := _KEYWORD_ARGUMENT.match(arguments[-1]):
        return next(
            (
                parameter
                for parameter in parameters
                if parameter.name == keyword_argument["name"]
                or parameter.kind is inspect.Parameter.VAR_KEYWORD
            ),
            None,
        )

    positional = [
        parameter
        for parameter in parameters
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if (index := len(arguments) - 1) < len(positional):
        return positional[index]

    return next(
        (
            parameter
            for parameter in parameters
            if parameter.kind is inspect.Parameter.VAR_POSITIONAL
        ),
        None,
    )


def _complete_keyword_arguments(
    namespace: dict[str, Any], code: str, token: str
) -> list[str]:
    """Return keyword arguments of the open call matching the argument typed."""
    if (
        (call := _find_open_call(code)) is None
        or call.arguments[-1].strip() != token
        or (signature := _signature(namespace, call.callee)) is None
    ):
        return []

    # Leave out what the arguments before this one already fill.
    given = call.arguments[:-1]
    keywords = {
        match["name"]
        for argument in given
        if (match := _KEYWORD_ARGUMENT.match(argument))
    }
    positional = len(given) - len(keywords)

    names: list[str] = []
    for index, parameter in enumerate(signature.parameters.values()):
        if (
            parameter.kind
            in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
            and parameter.name.startswith(token)
            and parameter.name not in keywords
            and not (
                parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
                and index < positional
            )
        ):
            names.append(f"{parameter.name}=")

    return names


def _complete_namespace(namespace: dict[str, Any], token: str) -> list[str]:
    """Return completions for a name or dotted attribute path."""
    if not token:
        return []

    expression, dot, prefix = token.rpartition(".")
    if not dot:
        return _complete_global(namespace, token)

    if (value := _resolve(namespace, expression)) is _MISSING:
        return []

    matches: list[str] = []
    for name in sorted(_static_names(value)):
        if not _is_completion(name, prefix):
            continue

        static = static_attribute(value, name)
        call = "(" if callable(static) or issubclass(type(static), classmethod) else ""
        matches.append(f"{expression}.{name}{call}")
        if len(matches) >= MAX_COMPLETIONS:
            break

    return matches


def _complete_global(namespace: dict[str, Any], prefix: str) -> list[str]:
    """Return completions for a name: keywords, then names, then builtins.

    Like rlcompleter, but without reading signatures of callables, which can
    run code of the user.
    """
    matches = [word for word in keyword.kwlist if word.startswith(prefix)]
    seen: set[str] = set()

    for names in _global_names(namespace):
        for name, value in names.items():
            if name in seen or not _is_completion(name, prefix):
                continue

            seen.add(name)
            matches.append(f"{name}(" if callable(value) else name)
            if len(matches) >= MAX_COMPLETIONS:
                return matches

    return matches


def _global_names(namespace: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return the names of the console, then the builtins, as plain strings.

    Code can store a subclass of str as a name, like in globals(), whose own
    __hash__ and __eq__ would run when looking up or matching names.
    """
    return (
        with_string_names(dict.items(namespace)),
        instance_dict(builtins) or {},
    )


def _static_names(value: Any) -> set[str]:
    """Return the attribute names of a value, like dir() without __dir__."""
    names = set(instance_dict(value) or {})
    for cls in class_mro(value if is_class(value) else type(value)):
        names.update(class_dict(cls))

    return names


@cache
def _top_level_modules() -> frozenset[str]:
    """Return the names of all importable top level modules.

    Cached, as scanning every path for modules is slow and rarely changes.
    """
    return frozenset(sys.builtin_module_names) | _list_modules(_search_path())


def _complete_module(path: str) -> list[str]:
    """Return completions for a dotted module path."""
    parent, _, prefix = path.rpartition(".")
    if not parent:
        names: Iterable[str] = _top_level_modules()
    elif (locations := _package_locations(parent)) is None:
        return []
    else:
        names = _list_modules(locations)

    return sorted(
        f"{parent}.{name}" if parent else name
        for name in names
        if _is_completion(name, prefix)
    )


def _complete_module_attribute(module_name: str, prefix: str) -> list[str]:
    """Return completions for names to import from a module.

    Names in a module are only known once it is imported; this lists those of
    imported modules, and submodules of any package.
    """
    names: set[str] = set()
    if (module := _imported_modules().get(module_name)) is not None:
        names.update(instance_dict(module) or {})

    if (locations := _package_locations(module_name)) is not None:
        names.update(_list_modules(locations))

    return sorted(name for name in names if _is_completion(name, prefix))


def _package_locations(name: str) -> list[str] | None:
    """Return where the submodules of a package are, without importing it.

    Importing runs the code of a module, which completion must not do.
    """
    if (module := _imported_modules().get(name)) is not None:
        locations = (instance_dict(module) or {}).get("__path__")
        if locations is None:
            return None

        # Only a plain list, as a package can set an iterable of its own. Others,
        # like those of namespace packages, are looked up like any package.
        if type(locations) is list:
            return [location for location in locations if type(location) is str]

    parent, _, child = name.rpartition(".")
    search_path = _package_locations(parent) if parent else _search_path()
    if search_path is None:
        return None

    # Like the import system finds them, but from disk only: it runs finders
    # and hooks that code can register.
    namespace = []
    for location in search_path:
        folder = os.path.join(location, child)
        if os.path.isfile(os.path.join(folder, "__init__.py")):
            return [folder]

        if os.path.isdir(folder):
            namespace.append(folder)

    return namespace or None


def _imported_modules() -> dict[str, Any]:
    """Return the imported modules, by names that are a str.

    Code can add one by a subclass of str, whose own __eq__ would run when
    looking up another module with the same hash.
    """
    return with_string_names(dict.items(sys.modules))


def _search_path() -> list[str]:
    """Return the folders top level modules are imported from."""
    if type(sys.path) is not list:
        return []

    return [location for location in sys.path if type(location) is str]


def _list_modules(locations: Iterable[str]) -> set[str]:
    """Return the modules and packages in folders, read from disk only.

    Like pkgutil.iter_modules, which runs finders and hooks that code can
    register. Packages in zip files are left out.
    """
    names: set[str] = set()
    for location in locations:
        try:
            entries = list(os.scandir(location or "."))
        except OSError:
            continue

        for entry in entries:
            # Any folder is a package, without an __init__.py a namespace one.
            if entry.is_dir():
                if entry.name != "__pycache__":
                    names.add(entry.name)

                continue

            for suffix in _MODULE_SUFFIXES:
                if entry.name.endswith(suffix):
                    names.add(entry.name.removesuffix(suffix))
                    break

    return {name for name in names if name.isidentifier() and name != "__init__"}


def _is_completion(name: str, prefix: str) -> bool:
    """Return if a name completes the prefix, hiding private names like Python."""
    return name.startswith(prefix) and (
        prefix.startswith("_") or not name.startswith("_")
    )
