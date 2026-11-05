"""Tests for completion and signature hints of the Debug console."""

from collections.abc import Generator, Iterator
from pathlib import Path
import sys
import types
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.typing import MockHAClientWebSocket

from homeassistant.components.debug_console.completion import _top_level_modules

from . import async_execute, async_send

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
empty_holder = Holder()

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
        pytest.param(
            "empty_holder.inner.al", "empty_holder.inner.al", [], id="unset_slot"
        ),
        pytest.param(
            "Thing.al", "Thing.al", ["Thing.alpha", "Thing.alps("], id="class"
        ),
        pytest.param(
            "Thing.nothing.al", "Thing.nothing.al", [], id="missing_attribute"
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

def wraps_itself(value):
    pass

wraps_itself.__wrapped__ = wraps_itself

import inspect

# Annotations of an explicit signature are not read as strings.
class Signed:
    __signature__ = inspect.Signature(
        [
            inspect.Parameter(
                "given", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int
            )
        ],
        return_annotation=int,
    )

@functools.wraps(inner)
def resigned(*args, **kwargs):
    pass

resigned.__signature__ = inspect.Signature(
    [inspect.Parameter("only", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
)

class Registry(type):
    def lookup(cls, key):
        pass

class Registered(metaclass=Registry):
    pass

class Plain:
    def act(self, value):
        pass

# Functions stored on an instance are not bound, like for getattr.
plain = Plain()
plain.act = Plain.act

# Annotations stored as text, like with `from __future__ import annotations`.
def stringly(value, other=1):
    pass

stringly.__annotations__ = {"value": "int", "other": "int", "return": "str"}

class WithNew:
    def __new__(cls, value):
        return super().__new__(cls)

class DecoratedInit:
    @functools.wraps(inner)
    def __init__(self, *args, **kwargs):
        pass

class Thing:
    def method(self, entity_id: str, *values: int, force: bool = False, **extra) -> str:
        \"\"\"Do the thing.

        In more detail.
        \"\"\"

    @functools.wraps(method)
    def decorated_method(self, *args, **kwargs):
        pass

    @property
    def getter(self):
        raise AssertionError("Properties must not be evaluated")

thing = Thing()
"""


# Without annotations: getting those runs code, as they are evaluated lazily.
METHOD_SIGNATURE = {
    "name": "method",
    "parameters": ["entity_id", "*values", "force=False", "**extra"],
    "returns": None,
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
            "wraps_itself(",
            {
                "name": "wraps_itself",
                "parameters": ["value"],
                "active": 0,
                "returns": None,
                "doc": "",
            },
            id="wraps_itself",
        ),
        pytest.param(
            "Signed(",
            {
                "name": "Signed",
                "parameters": ["given"],
                "active": 0,
                "returns": None,
                "doc": "",
            },
            id="class_signature",
        ),
        pytest.param(
            "resigned(",
            {
                "name": "resigned",
                "parameters": ["only"],
                "active": 0,
                "returns": None,
                "doc": "Do the inner thing.",
            },
            id="wrapper_signature",
        ),
        pytest.param(
            "stringly(",
            {
                "name": "stringly",
                "parameters": ["value: int", "other: int = 1"],
                "active": 0,
                "returns": "str",
                "doc": "",
            },
            id="text_annotations",
        ),
        pytest.param(
            "Registered.lookup(",
            {
                "name": "lookup",
                "parameters": ["key"],
                "active": 0,
                "returns": None,
                "doc": "",
            },
            id="metaclass_method",
        ),
        pytest.param(
            "plain.act(",
            {
                "name": "act",
                "parameters": ["self", "value"],
                "active": 0,
                "returns": None,
                "doc": "",
            },
            id="function_on_instance",
        ),
        pytest.param(
            "WithNew(",
            {
                "name": "WithNew",
                "parameters": ["value"],
                "active": 0,
                "returns": None,
                "doc": "",
            },
            id="class_new",
        ),
        pytest.param(
            "DecoratedInit(",
            {
                "name": "DecoratedInit",
                "parameters": ["*args", "**kwargs"],
                "active": 0,
                "returns": None,
                "doc": "",
            },
            id="decorated_init",
        ),
        pytest.param(
            "thing.decorated_method(",
            {**METHOD_SIGNATURE, "name": "decorated_method", "active": 0},
            id="decorated_method",
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
        pytest.param(
            {"type": "debug_console/complete", "code": "masked.me"},
            id="complete_class_property",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "masked.method("},
            id="signature_class_property",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "odd_dict.x"},
            id="complete_dict_class_property",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "holds_masked.it"},
            id="complete_attribute_class_property",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "Documented("},
            id="signature_doc_descriptor",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "holds_watched.item.al"},
            id="complete_descriptor_metaclass",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "FakeWrapper("},
            id="signature_wrapped_descriptor",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "bound_trap("},
            id="signature_bound_callable",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "SignatureTrap("},
            id="signature_class_signature",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "InheritsSignatureTrap("},
            id="signature_inherited_signature",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "SignatureTrap(a"},
            id="keywords_class_signature",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "InitTrap("},
            id="signature_init_descriptor",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "NewTrap("},
            id="signature_new_descriptor",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "PartialTrap("},
            id="signature_partialmethod",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "InitSignatureTrap("},
            id="signature_init_signature",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "function_signature_trap("},
            id="signature_function_signature",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "holds_equal.item.x"},
            id="complete_metaclass_equality",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "loud_annotation("},
            id="signature_annotation_format",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "loud_dict_holder.al"},
            id="complete_dict_subclass",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "loud_dict_holder.alpha.re"},
            id="resolve_dict_subclass",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "loud_na"},
            id="complete_global_name_subclass",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "named_holder.lo"},
            id="complete_attribute_name_subclass",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "named_holder.beta.re"},
            id="resolve_colliding_name",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "colliding_global.de"},
            id="resolve_colliding_global",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "colliding_function("},
            id="signature_colliding_global",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "shadowing.function("},
            id="signature_function_own_get",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "shadowing.static.x"},
            id="resolve_staticmethod_own_get",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "shadowing.klass("},
            id="signature_classmethod_own_get",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "doc_method("},
            id="signature_method_doc",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "defaults_trap("},
            id="signature_default_containers",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "defaults_trap(c"},
            id="keywords_default_containers",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "evaluated_annotation("},
            id="signature_annotation",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "evaluated_annotation(v"},
            id="keywords_annotation",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "text_signature_trap("},
            id="signature_text_signature",
        ),
        pytest.param(
            {"type": "debug_console/signature", "code": "parameter_trap("},
            id="signature_parameter_subclass",
        ),
        pytest.param(
            {"type": "debug_console/complete", "code": "parameter_trap(v"},
            id="keywords_parameter_subclass",
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

class Masked:
    @property
    def __class__(self):
        ran.append("__class__")
        return Masked

    def method(self, argument):
        pass

class OddDict:
    __dict__ = Masked()

class HoldsMasked:
    item = Masked()

class Documented:
    __doc__ = Descriptor()

    def __init__(self, argument):
        pass

masked = Masked()
odd_dict = OddDict()
holds_masked = HoldsMasked()

class HoldsWatched:
    item = Watched()

class FakeWrapper:
    __wrapped__ = Descriptor()

    def __init__(self, argument):
        pass

import types

holds_watched = HoldsWatched()

class SignatureTrap:
    __signature__ = Descriptor()

class InheritsSignatureTrap(SignatureTrap):
    pass

class InitTrap:
    __init__ = Descriptor()

class NewTrap:
    __new__ = Descriptor()

class PartialTrap:
    __partialmethod__ = Descriptor()

def init_with_masked_signature(self, argument):
    pass

init_with_masked_signature.__signature__ = masked

class InitSignatureTrap:
    __init__ = init_with_masked_signature

def function_signature_trap(argument):
    pass

function_signature_trap.__signature__ = masked

class EqualToEverything(type):
    def __eq__(cls, other):
        ran.append("metaclass eq")
        return True

    __hash__ = type.__hash__

class EqualDescriptor(metaclass=EqualToEverything):
    def __get__(self, instance, owner):
        ran.append("equal descriptor")

class HoldsEqual:
    item = EqualDescriptor()

holds_equal = HoldsEqual()

class Loud:
    def __format__(self, spec):
        ran.append("format")
        return "loud"

    def __str__(self):
        ran.append("str")
        return "loud"

import inspect

def loud_annotation(value):
    pass

class LoudDict(dict):
    def __bool__(self):
        ran.append("dict bool")
        return True

    def __contains__(self, key):
        ran.append("dict contains")
        return super().__contains__(key)

    def __getitem__(self, key):
        ran.append("dict getitem")
        return super().__getitem__(key)

    def __iter__(self):
        ran.append("dict iter")
        return super().__iter__()

    def keys(self):
        ran.append("dict keys")
        return super().keys()

class LoudDictHolder:
    pass

loud_dict_holder = LoudDictHolder()
loud_dict_holder.__dict__ = LoudDict(alpha=1)

class LoudName(str):
    def __hash__(self):
        ran.append("name hash")
        return super().__hash__()

    def __eq__(self, other):
        ran.append("name eq")
        return super().__eq__(other)

    def startswith(self, prefix, *args):
        ran.append("name startswith")
        return super().startswith(prefix, *args)

class CollidingName(LoudName):
    def __new__(cls, value, collides_with):
        name = super().__new__(cls, value)
        name.collides_with = collides_with
        return name

    def __hash__(self):
        ran.append("name hash")
        return hash(self.collides_with)

# Stored first, so looking up the names they collide with compares them.
globals()[CollidingName("decoy", "colliding_global")] = 1
globals()[CollidingName("decoy", "colliding_function")] = 1
class CollidingTarget:
    detail = 1

colliding_global = CollidingTarget()

def colliding_function(value):
    pass

globals()[LoudName("loud_name")] = 1

class NamedHolder:
    pass

named_holder = NamedHolder()
named_holder.__dict__[LoudName("loud_attribute")] = 1
named_holder.__dict__[CollidingName("gamma", "beta")] = 1
named_holder.beta = 1

def own_get(*args):
    ran.append("own get")

def shadowed_function(self, value):
    pass

shadowed_function.__get__ = own_get
shadowed_static = staticmethod(lambda value: None)
shadowed_static.__get__ = own_get
shadowed_class = classmethod(lambda cls, value: None)
shadowed_class.__get__ = own_get

class Shadowing:
    function = shadowed_function
    static = shadowed_static
    klass = shadowed_class

shadowing = Shadowing()

class DocTrap:
    __doc__ = Descriptor()

doc_method = types.MethodType(DocTrap, object())

class LoudTuple(tuple):
    def __len__(self):
        ran.append("tuple len")
        return super().__len__()

    def __getitem__(self, index):
        ran.append("tuple getitem")
        return super().__getitem__(index)

    def __iter__(self):
        ran.append("tuple iter")
        return super().__iter__()

class LoudKeywordDefaults(dict):
    def get(self, key, default=None):
        ran.append("kwdefaults get")
        return super().get(key, default)

    def __getitem__(self, key):
        ran.append("kwdefaults getitem")
        return super().__getitem__(key)

    def __contains__(self, key):
        ran.append("kwdefaults contains")
        return super().__contains__(key)

def defaults_trap(alpha, beta=1, *, charlie=2):
    pass

defaults_trap.__defaults__ = LoudTuple((1,))
defaults_trap.__kwdefaults__ = LoudKeywordDefaults({LoudName("charlie"): 2})

class AnnotationTrap:
    @property
    def state(self):
        ran.append("annotation")
        return int

annotation_trap = AnnotationTrap()

def evaluated_annotation(value: annotation_trap.state):
    pass

class Truthy:
    def __bool__(self):
        ran.append("bool")
        return False

def text_signature_trap(value):
    pass

text_signature_trap.__text_signature__ = Truthy()

class LoudParameter(inspect.Parameter):
    @property
    def kind(self):
        ran.append("parameter")
        return inspect.Parameter.POSITIONAL_OR_KEYWORD

def parameter_trap(value):
    pass

parameter_trap.__signature__ = inspect.Signature(
    [LoudParameter("value", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
)

loud_annotation.__signature__ = inspect.Signature(
    [
        inspect.Parameter(
            "value", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Loud()
        )
    ]
)
bound_trap = types.MethodType(callable_trap, object())

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
        pytest.param("import json.decoder.x", [], id="imported_module"),
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
    "code",
    [
        pytest.param(
            "def target(value):\n    pass\n\n"
            "target.__text_signature__ = '(value=debug_console_trap.holder.state)'",
            id="function",
        ),
        pytest.param(
            'class target:\n    """target(value=debug_console_trap.holder.state)\n'
            '--\n\n"""',
            id="class",
        ),
    ],
)
async def test_signature_does_not_evaluate_text_signature(
    websocket_client: MockHAClientWebSocket, code: str
) -> None:
    """Test the defaults in a text signature are not evaluated while typing."""
    evaluated = []

    class Holder:
        @property
        def state(self) -> int:
            evaluated.append(True)
            return 1

    module = types.ModuleType("debug_console_trap")
    module.holder = Holder()  # type: ignore[attr-defined]
    await async_execute(websocket_client, code)

    with patch.dict(sys.modules, {"debug_console_trap": module}):
        await async_send(
            websocket_client, {"type": "debug_console/signature", "code": "target("}
        )

    assert not evaluated


async def test_import_completion_runs_no_finders(
    websocket_client: MockHAClientWebSocket, tmp_path: Path
) -> None:
    """Test completing imports reads the disk, without finders or path hooks."""
    called = []

    class RecordingFinder:
        def find_spec(self, *args: Any, **kwargs: Any) -> None:
            called.append("finder")

        def iter_modules(self, prefix: str = "") -> Iterator[Any]:
            called.append("finder")
            return iter(())

    def recording_hook(path: str) -> None:
        called.append("hook")
        raise ImportError

    package = tmp_path / "debug_console_found"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "submodule.py").write_text("")
    # Namespace packages, without an __init__.py.
    (package / "nested").mkdir()
    (package / "nested" / "leaf.py").write_text("")
    (tmp_path / "debug_console_namespace").mkdir()
    (tmp_path / "debug_console_namespace" / "inner.py").write_text("")

    async def _async_complete(code: str) -> list[str]:
        result = await async_send(
            websocket_client, {"type": "debug_console/complete", "code": code}
        )
        return result["matches"]

    # Top level modules are cached, and these are only on this search path.
    _top_level_modules.cache_clear()
    try:
        with (
            patch.object(sys, "path", [str(tmp_path)]),
            patch.object(sys, "path_hooks", [recording_hook]),
            patch.dict(sys.path_importer_cache, {str(tmp_path): RecordingFinder()}),
        ):
            assert await _async_complete("import debug_console_f") == [
                "debug_console_found"
            ]
            assert await _async_complete("import debug_console_n") == [
                "debug_console_namespace"
            ]
            assert await _async_complete("import debug_console_found.") == [
                "debug_console_found.nested",
                "debug_console_found.submodule",
            ]
            assert await _async_complete("import debug_console_found.nested.l") == [
                "debug_console_found.nested.leaf"
            ]
            assert await _async_complete("import debug_console_namespace.i") == [
                "debug_console_namespace.inner"
            ]
    finally:
        _top_level_modules.cache_clear()

    assert not called


async def test_import_completion_with_odd_search_path(
    websocket_client: MockHAClientWebSocket, tmp_path: Path
) -> None:
    """Test a search path that is not a plain list is not used."""
    package = tmp_path / "debug_console_found"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "submodule.py").write_text("")

    with patch.object(sys, "path", (str(tmp_path),)):
        result = await async_send(
            websocket_client,
            {"type": "debug_console/complete", "code": "import debug_console_found.s"},
        )

    assert result["matches"] == []


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("import debug_console_absent.x", id="import"),
        pytest.param("from debug_console_absent import x", id="from_import"),
    ],
)
async def test_import_completion_with_odd_module_names(
    websocket_client: MockHAClientWebSocket, code: str
) -> None:
    """Test completing imports never compares names of modules that are odd."""
    compared = []

    class CollidingName(str):
        __slots__ = ()

        def __hash__(self) -> int:
            return hash("debug_console_absent")

        def __eq__(self, other: object) -> bool:
            compared.append(True)
            return False

    with patch.dict(sys.modules, {CollidingName("decoy"): types.ModuleType("decoy")}):
        compared.clear()
        result = await async_send(
            websocket_client, {"type": "debug_console/complete", "code": code}
        )
        assert not compared

    assert result["matches"] == []


async def test_import_completion_with_path_of_its_own(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test completing a submodule never iterates a path a package set itself."""
    iterated = []

    class LoudPath(list[str]):
        def __iter__(self):
            iterated.append(True)
            return super().__iter__()

    package = types.ModuleType("debug_console_loud")
    package.__path__ = LoudPath()
    with patch.dict(sys.modules, {"debug_console_loud": package}):
        result = await async_send(
            websocket_client,
            {"type": "debug_console/complete", "code": "import debug_console_loud.x"},
        )

    assert result["matches"] == []
    assert not iterated


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
