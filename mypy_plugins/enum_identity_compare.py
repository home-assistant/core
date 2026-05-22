"""Mypy plugin: flag ``==``/``!=`` between two operands of the same enum class.

Scope is intentionally narrow: only **plain ``enum.Enum`` subclasses** are
flagged by default, because Python's ``Enum.__eq__`` is identity-based —
``a == b`` and ``a is b`` produce the same result there.

``StrEnum``/``IntEnum``/``ReprEnum`` are **skipped** because their
``__eq__`` delegates to the underlying ``str``/``int`` and accepts raw
primitive values: callers routinely pass ``"on"`` where a ``HVACMode``
parameter is annotated, and ``==`` silently makes that work while ``is``
silently breaks it. Switching those sites to ``is`` is a runtime-behavior
change, not a refactor.

A small allowlist (``_FRAMEWORK_GUARANTEED_ENUMS``) carves back in
``StrEnum``/``IntEnum`` classes where the HA framework itself controls
every callsite and guarantees the value is the enum instance — currently
just ``homeassistant.data_entry_flow.FlowResultType``.

``enum.Flag``/``enum.IntFlag`` are always exempt — bitwise ``==`` is
idiomatic there.

Usage: add to ``mypy.ini``::

    [mypy]
    plugins = mypy_plugins.enum_identity_compare
"""

from collections.abc import Callable

from mypy.errorcodes import ErrorCode
from mypy.nodes import TypeInfo
from mypy.plugin import MethodContext, Plugin
from mypy.types import Instance, LiteralType, Type, UnionType, get_proper_type

ENUM_IDENTITY = ErrorCode(
    "ha-enum-identity-compare",
    "Use `is`/`is not` to compare two operands of the same enum class.",
    "Home Assistant",
)

_PLAIN_ENUM_BASE = "enum.Enum"
_VALUE_BASED_ENUM_BASES = frozenset(
    {"enum.IntEnum", "enum.ReprEnum", "enum.StrEnum"}
)
_FLAG_BASES = frozenset({"enum.Flag", "enum.IntFlag"})

# StrEnum/IntEnum classes where every callsite assigning the value is
# framework-controlled, so the runtime value is guaranteed to be the
# enum instance (never a raw string/int). Audited additions only.
_FRAMEWORK_GUARANTEED_ENUMS = frozenset(
    {
        "homeassistant.data_entry_flow.FlowResultType",
    }
)


def _enum_class(t: Type | None) -> TypeInfo | None:
    """Return the enum TypeInfo if t resolves to a tracked enum class.

    Handles three shapes:
    - ``Instance``: the direct case, e.g. ``source: SourceCodes``.
    - ``LiteralType``: a single literal enum member, e.g. ``Literal[E.A]``.
      Peeled to its enum-class ``fallback``.
    - ``UnionType``: if all variants resolve to the same enum class, that
      class is passed on.

    Returns ``None`` for:
    - ``Flag``/``IntFlag`` (bitwise ``==`` is idiomatic)
    - ``StrEnum``/``IntEnum``/``ReprEnum`` not in the framework allowlist
    - Anything else (``Any``, ``None``, mixed unions, etc.)
    """
    if t is None:
        return None
    pt = get_proper_type(t)
    if isinstance(pt, UnionType):
        common: TypeInfo | None = None
        for variant in pt.items:
            v_info = _enum_class(variant)
            if v_info is None:
                return None
            if common is None:
                common = v_info
            elif common.fullname != v_info.fullname:
                return None
        return common
    if isinstance(pt, LiteralType):
        pt = pt.fallback
    if not isinstance(pt, Instance):
        return None
    info = pt.type
    has_enum_base = False
    has_value_based_base = False
    for base in info.mro:
        fn = base.fullname
        if fn in _FLAG_BASES:
            return None
        if fn in _VALUE_BASED_ENUM_BASES:
            has_value_based_base = True
        if fn == _PLAIN_ENUM_BASE:
            has_enum_base = True
    if not has_enum_base:
        return None
    if has_value_based_base and info.fullname not in _FRAMEWORK_GUARANTEED_ENUMS:
        # StrEnum/IntEnum without explicit trust — `is` may diverge from
        # `==` when callers pass the underlying string/int.
        return None
    return info


def _emit(ctx: MethodContext, op: str, enum_cls: TypeInfo) -> Type:
    """Emit the warning and return the default return type."""
    replacement = "is" if op == "==" else "is not"
    ctx.api.fail(
        f"Use `{replacement}` instead of `{op}` to compare "
        f"`{enum_cls.name}` enum instances",
        ctx.context,
        code=ENUM_IDENTITY,
    )
    return ctx.default_return_type


def _make_hook(op: str) -> Callable[[MethodContext], Type]:
    """Return a method-hook callback for ``__eq__`` (``==``) or ``__ne__``."""

    def hook(ctx: MethodContext) -> Type:
        left_enum = _enum_class(ctx.type)
        if left_enum is None:
            return ctx.default_return_type
        right_type = ctx.arg_types[0][0] if ctx.arg_types and ctx.arg_types[0] else None
        right_enum = _enum_class(right_type)
        if right_enum is None:
            return ctx.default_return_type
        if left_enum.fullname != right_enum.fullname:
            return ctx.default_return_type
        return _emit(ctx, op, left_enum)

    return hook


_EQ_HOOK = _make_hook("==")
_NE_HOOK = _make_hook("!=")


class HassEnumIdentityPlugin(Plugin):
    """Mypy plugin entry point."""

    def get_method_hook(self, fullname: str) -> Callable[[MethodContext], Type] | None:
        """Return a hook for ``__eq__``/``__ne__`` calls, else ``None``.

        ``a == b`` desugars to ``a.__eq__(b)``; ``a != b`` to ``__ne__``.
        Mypy reports the method's fullname, which we use to tell which
        operator triggered the call.
        """
        if fullname.endswith(".__eq__"):
            return _EQ_HOOK
        if fullname.endswith(".__ne__"):
            return _NE_HOOK
        return None


def plugin(version: str) -> type[Plugin]:
    """Mypy plugin entry point."""
    return HassEnumIdentityPlugin
