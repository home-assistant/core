"""Mypy plugin: flag ``==``/``!=`` between two operands of the same enum class.

Mypy already resolves the full type of expressions like ``result["type"]``
when the surrounding code is typed (``ConfigFlowResult`` TypedDict, etc.),
so we can reliably tell whether *both* sides of a comparison are the same
enum class — something astroid struggles with.

When both sides resolve to the same ``enum.Enum`` subclass (excluding
``enum.Flag``/``enum.IntFlag`` where bitwise ``==`` is idiomatic), the
plugin emits an error suggesting ``is``/``is not``.

Usage: add to ``mypy.ini``::

    [mypy]
    plugins = mypy_plugins.enum_identity_compare
"""

from collections.abc import Callable

from mypy.errorcodes import ErrorCode
from mypy.nodes import TypeInfo
from mypy.plugin import MethodContext, Plugin
from mypy.types import Instance, Type, get_proper_type

ENUM_IDENTITY = ErrorCode(
    "ha-enum-identity-compare",
    "Use `is`/`is not` to compare two operands of the same enum class.",
    "Home Assistant",
)

_ENUM_BASES = frozenset({"enum.Enum", "enum.IntEnum", "enum.ReprEnum", "enum.StrEnum"})
_FLAG_BASES = frozenset({"enum.Flag", "enum.IntFlag"})


def _enum_class(t: Type | None) -> TypeInfo | None:
    """Return the enum TypeInfo if t is an Instance of an enum subclass.

    Returns ``None`` for ``Flag``/``IntFlag`` (bitwise ``==`` is idiomatic).
    """
    if t is None:
        return None
    pt = get_proper_type(t)
    if not isinstance(pt, Instance):
        return None
    info = pt.type
    found = False
    for base in info.mro:
        if base.fullname in _FLAG_BASES:
            return None
        if base.fullname in _ENUM_BASES:
            found = True
    return info if found else None


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
