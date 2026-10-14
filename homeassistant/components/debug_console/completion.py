"""Completion and signature hints for code typed in the Debug console.

All of this runs while typing, so it never reads attributes in a way that runs
user code, such as properties, descriptors, or __getattr__.
"""

from annotationlib import Format
import builtins
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
import importlib
import inspect
from itertools import pairwise
import pkgutil
import re
import rlcompleter
import sys
import types
from typing import Any

from homeassistant.core import HomeAssistant

from .inspection import preview

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

    # Finding modules scans the disk and may import packages, so not in the loop.
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
    doc = inspect.getdoc(_resolve(namespace, call.callee)) or ""

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
            quote = (
                code[index : index + 3]
                if code[index : index + 3] in ('"""', "'''")
                else char
            )
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
        static = inspect.getattr_static(value, attribute, _MISSING)
        if static is _MISSING:
            return _MISSING

        owner = value if isinstance(value, type) else type(value)
        from_class = static is inspect.getattr_static(owner, attribute, _MISSING)
        if not from_class or not hasattr(type(static), "__get__"):
            # Plain values, including those in the __dict__ of an instance.
            value = static
        elif isinstance(static, _SAFE_DESCRIPTORS):
            instance = None if value is owner else value
            value = static.__get__(instance, owner)  # pylint: disable=unnecessary-dunder-call
        elif isinstance(static, types.MemberDescriptorType) and value is not owner:
            value = static.__get__(value, owner)  # pylint: disable=unnecessary-dunder-call
        else:
            return _MISSING
    return value


def _signature(namespace: dict[str, Any], callee: str) -> inspect.Signature | None:
    """Return the signature of a callable, or None if it has none."""
    if (target := _resolve(namespace, callee)) is _MISSING or not callable(target):
        return None
    try:
        # As strings, as evaluating annotations can fail or import things.
        return inspect.signature(target, annotation_format=Format.STRING)
    except TypeError, ValueError:
        return None


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
        text = f"{text}{separator}{preview(parameter.default)}"
    return text


def _active_parameter(
    parameters: list[inspect.Parameter], arguments: list[str]
) -> inspect.Parameter | None:
    """Return the parameter the argument being typed goes to."""
    if keyword := _KEYWORD_ARGUMENT.match(arguments[-1]):
        return next(
            (
                parameter
                for parameter in parameters
                if parameter.name == keyword["name"]
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

    return [
        f"{parameter.name}="
        for parameter in signature.parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        and parameter.name.startswith(token)
    ]


def _complete_namespace(namespace: dict[str, Any], token: str) -> list[str]:
    """Return completions for a name or dotted attribute path."""
    if not token:
        return []

    expression, dot, prefix = token.rpartition(".")
    if not dot:
        return rlcompleter.Completer(namespace).global_matches(token)

    if (value := _resolve(namespace, expression)) is _MISSING:
        return []

    matches: list[str] = []
    for name in sorted(dir(value)):
        if _is_completion(name, prefix):
            static = inspect.getattr_static(value, name, None)
            call = "(" if callable(static) or isinstance(static, classmethod) else ""
            matches.append(f"{expression}.{name}{call}")
    return matches


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
    elif (package_path := _package_path(parent)) is None:
        return []
    else:
        names = [module.name for module in pkgutil.iter_modules(package_path)]

    return sorted(
        f"{parent}.{name}" if parent else name
        for name in names
        if _is_completion(name, prefix)
    )


def _complete_module_attribute(module_name: str, prefix: str) -> list[str]:
    """Return completions for names to import from a module."""
    try:
        module = importlib.import_module(module_name)
    except Exception:  # noqa: BLE001
        return []

    names = set(dir(module))
    if (package_path := getattr(module, "__path__", None)) is not None:
        names.update(submodule.name for submodule in pkgutil.iter_modules(package_path))

    return sorted(name for name in names if _is_completion(name, prefix))


def _package_path(name: str) -> list[str] | None:
    """Import a package and return its search path, or None if not a package."""
    try:
        package = importlib.import_module(name)
    except Exception:  # noqa: BLE001
        return None
    return getattr(package, "__path__", None)


def _is_completion(name: str, prefix: str) -> bool:
    """Return if a name completes the prefix, hiding private names like Python."""
    return name.startswith(prefix) and (
        prefix.startswith("_") or not name.startswith("_")
    )
