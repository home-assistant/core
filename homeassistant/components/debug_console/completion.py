"""Completion and signature hints for code typed in the Debug console.

All of this runs while typing, so it never runs user code: no properties,
descriptors, __getattr__, or __dir__, and no importing modules.
"""

from abc import ABCMeta
from annotationlib import Format
import builtins
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from importlib.machinery import PathFinder
import inspect
from itertools import pairwise
import keyword
import pkgutil
import re
import sys
import types
from typing import Any, cast

from homeassistant.core import HomeAssistant

from .inspection import (
    class_dict,
    class_mro,
    instance_dict,
    is_class,
    preview,
    static_attribute,
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
    types.MethodType,
    types.MethodDescriptorType,
    types.WrapperDescriptorType,
    types.MethodWrapperType,
    types.ClassMethodDescriptorType,
)

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
    # Not inspect.getdoc, which also searches classes when the doc is missing.
    # Reading __doc__ of a class runs a descriptor stored there, so read it
    # from the class itself.
    value = _resolve(namespace, call.callee)
    doc = class_dict(value).get("__doc__") if is_class(value) else value.__doc__
    doc = inspect.cleandoc(doc) if type(doc) is str else ""

    return {
        "name": call.callee.rpartition(".")[2],
        "parameters": [_format_parameter(parameter) for parameter in parameters],
        "active": None if active is None else parameters.index(active),
        "returns": None
        if signature.return_annotation is inspect.Signature.empty
        else signature.return_annotation,
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

    if first in namespace:
        value = namespace[first]
    elif hasattr(builtins, first):
        value = getattr(builtins, first)
    else:
        return _MISSING

    # Without getattr(), as properties, descriptors, and __getattr__ run code.
    for attribute in attributes:
        static = static_attribute(value, attribute, _MISSING)
        if static is _MISSING:
            return _MISSING

        owner = value if is_class(value) else type(value)
        from_class = static is static_attribute(owner, attribute, _MISSING)
        if not from_class or not hasattr(type(static), "__get__"):
            # Plain values, including those in the __dict__ of an instance.
            value = static
        elif type(static) in _SAFE_DESCRIPTORS:
            instance = None if value is owner else value
            value = static.__get__(instance, owner)  # pylint: disable=unnecessary-dunder-call
        elif type(static) is types.MemberDescriptorType and value is not owner:
            value = static.__get__(value, owner)  # pylint: disable=unnecessary-dunder-call
        else:
            return _MISSING

    return value


def _signature(namespace: dict[str, Any], callee: str) -> inspect.Signature | None:
    """Return the signature of a callable, or None if it has none."""
    if (target := _resolve(namespace, callee)) is _MISSING or not _has_safe_signature(
        target
    ):
        return None

    # Decorated functions show the signature of what they wrap, as long as that
    # is safe to read too.
    target = inspect.unwrap(
        target,
        # Only called for wrappers, which have __wrapped__.
        stop=lambda wrapper: not _has_safe_signature(cast(Any, wrapper).__wrapped__),
    )

    try:
        # As strings, as evaluating annotations can fail or import things.
        return inspect.signature(
            target, annotation_format=Format.STRING, follow_wrapped=False
        )
    except TypeError, ValueError:
        return None


def _has_safe_signature(value: Any) -> bool:
    """Return if inspect can read the signature without running user code.

    For other callable objects, and classes with a metaclass of their own,
    inspect reads attributes like __signature__, which can be properties.
    """
    if is_class(value):
        return type(value) in _STANDARD_METACLASSES

    return type(value) in _SIGNATURE_TYPES


def _format_parameter(parameter: inspect.Parameter) -> str:
    """Format a parameter like Python, without quoting its string annotation."""
    text = parameter.name
    if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
        text = f"*{text}"
    elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
        text = f"**{text}"

    if parameter.annotation is not inspect.Parameter.empty:
        text = f"{text}: {parameter.annotation}"

    if parameter.default is not inspect.Parameter.empty:
        separator = (
            " = " if parameter.annotation is not inspect.Parameter.empty else "="
        )
        text = f"{text}{separator}{_format_default(parameter.default)}"

    return text


def _format_default(value: Any) -> str:
    """Format a default value, without running a __repr__ of the user."""
    if type(value) in _SAFE_DEFAULT_TYPES:
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

    for names in (namespace, vars(builtins)):
        for name, value in names.items():
            if name in seen or not _is_completion(name, prefix):
                continue

            seen.add(name)
            matches.append(f"{name}(" if callable(value) else name)
            if len(matches) >= MAX_COMPLETIONS:
                return matches

    return matches


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
    return frozenset(sys.builtin_module_names) | {
        module.name for module in pkgutil.iter_modules()
    }


def _complete_module(path: str) -> list[str]:
    """Return completions for a dotted module path."""
    parent, _, prefix = path.rpartition(".")
    if not parent:
        names: Iterable[str] = _top_level_modules()
    elif (locations := _package_locations(parent)) is None:
        return []
    else:
        names = [module.name for module in pkgutil.iter_modules(locations)]

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
    if (module := sys.modules.get(module_name)) is not None:
        names.update(instance_dict(module) or {})

    if (locations := _package_locations(module_name)) is not None:
        names.update(submodule.name for submodule in pkgutil.iter_modules(locations))

    return sorted(name for name in names if _is_completion(name, prefix))


def _package_locations(name: str) -> list[str] | None:
    """Return where the submodules of a package are, without importing it.

    Importing runs the code of a module, which completion must not do.
    """
    if (module := sys.modules.get(name)) is not None:
        locations = (instance_dict(module) or {}).get("__path__")
        return None if locations is None else list(locations)

    parent = name.rpartition(".")[0]
    search_path = None
    if parent and (search_path := _package_locations(parent)) is None:
        return None

    spec = PathFinder.find_spec(name, search_path)
    if spec is None or spec.submodule_search_locations is None:
        return None

    return list(spec.submodule_search_locations)


def _is_completion(name: str, prefix: str) -> bool:
    """Return if a name completes the prefix, hiding private names like Python."""
    return name.startswith(prefix) and (
        prefix.startswith("_") or not name.startswith("_")
    )
