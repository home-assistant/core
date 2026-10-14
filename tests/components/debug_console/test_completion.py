"""Tests for completion and signature hints of the Debug console."""

from collections.abc import Generator
from pathlib import Path
import sys
from typing import Any
from unittest.mock import patch

import pytest

from . import async_execute, async_send

from tests.typing import MockHAClientWebSocket

COMPLETION_SETUP = """
class Thing:
    alpha = 1

    def alps(self, alpha, also=None):
        pass

    @property
    def getter(self):
        raise AssertionError("Properties must not run while completing")

class Holder:
    __slots__ = ("inner",)

class Shadowed:
    @property
    def value(self):
        raise AssertionError("Properties must not run while completing")

thing = Thing()
holder = Holder()
holder.inner = thing

class Box:
    pass

box = Box()
box.content = thing

# A property wins over an entry in the instance __dict__, like for getattr.
shadowed = Shadowed()
shadowed.__dict__["value"] = thing
"""


@pytest.mark.parametrize(
    ("line", "token", "expected"),
    [
        pytest.param("", "", [], id="empty"),
        pytest.param("x = ", "", [], id="no_token"),
        pytest.param("has", "has", ["hass", "hasattr(", "hash("], id="global"),
        pytest.param(
            "print(thing.al",
            "thing.al",
            ["thing.alpha", "thing.alps("],
            id="attribute",
        ),
        pytest.param("thing.ge", "thing.ge", ["thing.getter"], id="property"),
        pytest.param(
            "thing.alpha.re", "thing.alpha.re", ["thing.alpha.real"], id="plain_value"
        ),
        pytest.param(
            "holder.inner.alp",
            "holder.inner.alp",
            ["holder.inner.alpha", "holder.inner.alps("],
            id="slot",
        ),
        pytest.param("thing.getter.up", "thing.getter.up", [], id="through_property"),
        pytest.param(
            "shadowed.value.al", "shadowed.value.al", [], id="property_over_instance"
        ),
        pytest.param(
            "box.content.alp",
            "box.content.alp",
            ["box.content.alpha", "box.content.alps("],
            id="instance_attribute",
        ),
        pytest.param(
            "thing.alps(1, al", "al", ["also=", "all("], id="keyword_after_positional"
        ),
        pytest.param(
            "thing.alps(also=1, al",
            "al",
            ["alpha=", "all("],
            id="keyword_after_keyword",
        ),
        pytest.param("thing.alps(also=al", "al", ["all("], id="keyword_value"),
    ],
)
async def test_complete(
    websocket_client: MockHAClientWebSocket,
    line: str,
    token: str,
    expected: list[str],
) -> None:
    """Test completing names, attributes, and keyword arguments."""
    await async_execute(websocket_client, COMPLETION_SETUP)

    result = await async_send(
        websocket_client, {"type": "debug_console/complete", "code": line}
    )

    assert result == {"token": token, "matches": expected}


@pytest.mark.parametrize(
    ("line", "token", "expected"),
    [
        pytest.param("import jso", "jso", ["json"], id="import"),
        pytest.param(
            "import os, email.mi", "email.mi", ["email.mime"], id="import_submodule"
        ),
        pytest.param("from email.mi", "email.mi", ["email.mime"], id="from_module"),
        pytest.param("import email._", "email._", ["email._parseaddr"], id="private"),
        pytest.param("from json import du", "du", ["dump", "dumps"], id="from_name"),
        pytest.param(
            "from email import (charset, mi", "mi", ["mime"], id="from_submodule"
        ),
    ],
)
async def test_complete_modules(
    websocket_client: MockHAClientWebSocket,
    line: str,
    token: str,
    expected: list[str],
) -> None:
    """Test completing modules, and names to import from them."""
    result = await async_send(
        websocket_client, {"type": "debug_console/complete", "code": line}
    )

    assert result["token"] == token
    # Which modules there are depends on what is installed.
    assert set(expected) <= set(result["matches"])


@pytest.mark.parametrize(
    "line",
    [
        pytest.param("import doesnotexist.x", id="missing"),
        pytest.param("import doesnotexist.child.x", id="missing_parent"),
        pytest.param("import json.x", id="not_a_package"),
        pytest.param("from doesnotexist import x", id="from_missing"),
    ],
)
async def test_complete_no_modules(
    websocket_client: MockHAClientWebSocket, line: str
) -> None:
    """Test completing modules that do not exist."""
    result = await async_send(
        websocket_client, {"type": "debug_console/complete", "code": line}
    )

    assert result["matches"] == []


SIGNATURE_SETUP = """
import functools

def inner(alpha, beta=2):
    \"\"\"Do the inner thing.\"\"\"

@functools.wraps(inner)
def decorated(*args, **kwargs):
    pass

class Thing:
    def method(self, entity_id: str, *values: int, force: bool = False, **extra) -> str:
        \"\"\"Do the thing.

        In more detail.
        \"\"\"

    @property
    def getter(self):
        raise AssertionError("Properties must not be evaluated")

thing = Thing()
"""


METHOD_SIGNATURE = {
    "name": "method",
    "parameters": [
        "entity_id: str",
        "*values: int",
        "force: bool = False",
        "**extra",
    ],
    "returns": "str",
    "doc": "Do the thing.",
}


@pytest.mark.parametrize(
    ("code", "signature"),
    [
        pytest.param("thing.method(", {**METHOD_SIGNATURE, "active": 0}, id="first"),
        pytest.param(
            "thing.method('a, (b', ", {**METHOD_SIGNATURE, "active": 1}, id="string"
        ),
        pytest.param(
            "thing.method(\n    'a',\n    1,\n    2,\n",
            {**METHOD_SIGNATURE, "active": 1},
            id="var_positional",
        ),
        pytest.param(
            "thing.method('a', force=", {**METHOD_SIGNATURE, "active": 2}, id="keyword"
        ),
        pytest.param(
            "thing.method('a', other=", {**METHOD_SIGNATURE, "active": 3}, id="kwargs"
        ),
        pytest.param(
            "x = [thing.method(", {**METHOD_SIGNATURE, "active": 0}, id="nested"
        ),
        pytest.param("thing.method('a')", None, id="closed"),
        pytest.param("[1, ", None, id="not_a_call"),
        pytest.param("(1, ", None, id="parentheses"),
        pytest.param("unknown(", None, id="unknown"),
        pytest.param("thing.getter.x(", None, id="property"),
        pytest.param("thing(", None, id="not_callable"),
        pytest.param(
            "thing.method('a\\', b', ",
            {**METHOD_SIGNATURE, "active": 1},
            id="escaped_quote",
        ),
        pytest.param(
            "thing.method('a', # comment",
            {**METHOD_SIGNATURE, "active": 1},
            id="comment",
        ),
        pytest.param("min(", None, id="no_signature"),
        pytest.param(
            "decorated(",
            {
                "name": "decorated",
                "parameters": ["alpha", "beta=2"],
                "active": 0,
                "returns": None,
                "doc": "Do the inner thing.",
            },
            id="decorated",
        ),
        pytest.param(
            "Thing(",
            {
                "name": "Thing",
                "parameters": [],
                "active": None,
                "returns": None,
                "doc": "",
            },
            id="class",
        ),
        pytest.param(
            "len(",
            {
                "name": "len",
                "parameters": ["obj"],
                "active": 0,
                "returns": None,
                "doc": "Return the number of items in a container.",
            },
            id="builtin",
        ),
    ],
)
async def test_signature(
    websocket_client: MockHAClientWebSocket,
    code: str,
    signature: dict[str, Any] | None,
) -> None:
    """Test the signature of the call being typed."""
    await async_execute(websocket_client, SIGNATURE_SETUP)

    result = await async_send(
        websocket_client, {"type": "debug_console/signature", "code": code}
    )

    assert result == {"signature": signature}


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(
            {"type": "debug_console/complete", "code": "trap.descriptor.x"},
            id="complete_descriptor",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "trap.dynamic.x"},
            id="complete_getattr",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "trap.descriptor.x("},
            id="signature_descriptor",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "trap.dynamic("},
            id="signature_getattr",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "trap.de"}, id="complete_dir"
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "callable_trap("},
            id="signature_property",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "callable_trap(a"},
            id="keywords_property",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "with_default("},
            id="signature_default",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "callable_tr"},
            id="complete_global_callable",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "sneaky.method("},
            id="signature_descriptor_subclass",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "sneaky.method.x"},
            id="complete_descriptor_subclass",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "wraps_trap("},
            id="signature_wrapped_callable",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "WithMetaclass("},
            id="signature_metaclass",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "watched.al"},
            id="complete_metaclass_getattribute",
        ),
    ],
)
async def test_typing_runs_no_attribute_code(
    websocket_client: MockHAClientWebSocket, command: dict[str, Any]
) -> None:
    """Test completion and signatures never run user code of the objects."""
    await async_execute(
        websocket_client,
        """
ran = []

class Descriptor:
    def __get__(self, instance, owner):
        ran.append("descriptor")

class Trap:
    descriptor = Descriptor()

    def __getattr__(self, name):
        ran.append("getattr")

    def __dir__(self):
        ran.append("dir")
        return []

class CallableTrap:
    @property
    def __signature__(self):
        ran.append("signature")

    def __call__(self, argument):
        pass

class Default:
    def __repr__(self):
        ran.append("repr")
        return "Default()"

def with_default(value=Default()):
    pass

class SneakyStaticMethod(staticmethod):
    def __get__(self, instance, owner):
        ran.append("descriptor subclass")
        return super().__get__(instance, owner)

class Sneaky:
    method = SneakyStaticMethod(lambda: None)

class Metaclass(type):
    @property
    def __signature__(cls):
        ran.append("metaclass")

class WithMetaclass(metaclass=Metaclass):
    pass

trap = Trap()
callable_trap = CallableTrap()
sneaky = Sneaky()

import functools

@functools.wraps(callable_trap)
def wraps_trap(*args, **kwargs):
    pass

class WatchingMetaclass(type):
    def __getattribute__(cls, name):
        ran.append("metaclass getattribute")
        return super().__getattribute__(name)

class Watched(metaclass=WatchingMetaclass):
    alpha = 1

watched = Watched()

# Creating the classes above may run their hooks already.
ran.clear()
""",
    )

    await async_send(websocket_client, command)
    result = await async_execute(websocket_client, "ran")

    assert result["result"]["preview"] == "[]"


@pytest.fixture
def probe_package(tmp_path: Path) -> Generator[str]:
    """Provide a package on the module path, that must not get imported."""
    package = tmp_path / "debug_console_probe"
    (package / "submodule").mkdir(parents=True)
    (package / "__init__.py").write_text("raise AssertionError('imported')\n")
    (package / "submodule" / "__init__.py").write_text("")
    (package / "plain.py").write_text("raise AssertionError('imported')\n")
    with patch.object(sys, "path", [str(tmp_path), *sys.path]):
        yield "debug_console_probe"

    assert "debug_console_probe" not in sys.modules


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param(
            "import debug_console_probe.sub",
            ["debug_console_probe.submodule"],
            id="import",
        ),
        pytest.param(
            "from debug_console_probe import sub", ["submodule"], id="from_import"
        ),
        pytest.param(
            "import debug_console_probe.plain.inner.x", [], id="not_a_package"
        ),
    ],
)
@pytest.mark.usefixtures("probe_package")
async def test_import_completion_does_not_import(
    websocket_client: MockHAClientWebSocket, code: str, expected: list[str]
) -> None:
    """Test completing imports lists modules without running their code."""
    result = await async_send(
        websocket_client, {"type": "debug_console/complete", "code": code}
    )

    assert result["matches"] == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        pytest.param("thing.al", ["thing.alpha"], id="attribute"),
        pytest.param("has", ["hass"], id="global"),
    ],
)
async def test_complete_limited(
    websocket_client: MockHAClientWebSocket, line: str, expected: list[str]
) -> None:
    """Test completion stops at the maximum number of matches."""
    await async_execute(websocket_client, COMPLETION_SETUP)

    with patch("homeassistant.components.debug_console.completion.MAX_COMPLETIONS", 1):
        result = await async_send(
            websocket_client, {"type": "debug_console/complete", "code": line}
        )

    assert result["matches"] == expected


async def test_signature_hides_object_defaults(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test defaults that could bring their own __repr__ show as a placeholder."""
    await async_execute(
        websocket_client,
        "def function(number=1, text='a', other=object()):\n    pass\n",
    )

    result = await async_send(
        websocket_client, {"type": "debug_console/signature", "code": "function("}
    )

    assert result["signature"]["parameters"] == ["number=1", "text='a'", "other=…"]
