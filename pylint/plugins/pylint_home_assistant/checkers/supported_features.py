"""Checker: declared supported features must have their method implemented.

Entity platforms gate services on ``supported_features`` flags. For example
``cover`` registers::

    component.async_register_entity_service(
        SERVICE_OPEN_COVER, None, "async_open_cover", [CoverEntityFeature.OPEN]
    )

which means an entity that advertises ``CoverEntityFeature.OPEN`` **must**
implement ``async_open_cover`` (or its sync counterpart ``open_cover``). If it
does not, Home Assistant either raises ``NotImplementedError`` at runtime or
silently does nothing when the service is called.

Rather than hard-coding a feature -> method table, this checker derives the
mapping *per platform* by reading each platform's ``async_register_entity_service``
calls through astroid. The mapping is intentionally conservative -- it only
enforces a feature when we can prove which entity method backs it:

* the ``required_features`` argument must be a **single** flag (combinations
  such as ``[CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE]`` gate
  convenience methods like ``async_toggle`` that the base class already
  implements, so they are skipped);
* the service handler must resolve to an entity method whose **base
  implementation is trivial** (``raise NotImplementedError`` or an empty
  body). Handlers with real base implementations (e.g. ``async_toggle``)
  are skipped. One level of indirection is followed: a base dispatcher such
  as ``async_handle_set_preset_mode_service`` that forwards to a single
  public ``self.async_set_preset_mode(...)`` resolves to that method.

On the declaration side only *static* ``_attr_supported_features`` assignments
are inspected -- class body or plain ``self._attr_supported_features = ...``
assignments, with flags from all such assignments (including ones in
conditional branches) unioned, since any of them may be advertised at runtime.
Dynamic constructions -- ``|=``, a ``supported_features`` property, or a value
computed from a variable/call -- are treated as unknown and skipped, so the
checker never guesses.
"""

from functools import cache

import astroid
from astroid import MANAGER, nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import ENTITY_COMPONENTS
from pylint_home_assistant.helpers.ast_utils import extended_ancestors, safe_ancestors
from pylint_home_assistant.helpers.entity_class import (
    collect_same_module_ancestor_qnames,
    inherits_from_entity,
)

_COMPONENTS_ROOT = "homeassistant.components"
_ATTR = "_attr_supported_features"
_REGISTER = "async_register_entity_service"


def _counterpart(name: str) -> str:
    """Return the sync/async counterpart of a method name."""
    if name.startswith("async_"):
        return name[len("async_") :]
    return f"async_{name}"


def _candidate_methods(name: str) -> frozenset[str]:
    """A method requirement is satisfied by either the sync or async form."""
    return frozenset({name, _counterpart(name)})


def _platform_of(class_node: nodes.ClassDef) -> str | None:
    """Return the entity platform a class belongs to, via its base classes.

    Platform base entities (``CoverEntity``, ``VacuumEntity``, ...) live in
    ``homeassistant.components.<platform>`` -- either the package ``__init__``
    or a submodule such as ``valve/entity.py``. We match an ancestor defined
    anywhere in a known entity component's package.
    """
    for ancestor in extended_ancestors(class_node):
        module_name: str = ancestor.root().name
        if not module_name.startswith(f"{_COMPONENTS_ROOT}."):
            continue
        rest = module_name[len(_COMPONENTS_ROOT) + 1 :]
        platform = rest.split(".", 1)[0]
        if platform in ENTITY_COMPONENTS:
            return platform
    return None


def _is_trivial_body(func: nodes.FunctionDef) -> bool:
    """Return True if *func* has no real implementation.

    Trivial == empty, only a docstring, ``pass``, a bare/``None`` return, or
    ``raise NotImplementedError``. These are the abstract stubs an integration
    is expected to override.
    """
    body = list(func.body)
    if (
        body
        and isinstance(body[0], nodes.Expr)
        and isinstance(body[0].value, nodes.Const)
    ):
        body = body[1:]
    if not body:
        return True
    for stmt in body:
        if isinstance(stmt, nodes.Pass):
            continue
        if isinstance(stmt, nodes.Return) and (
            stmt.value is None
            or (isinstance(stmt.value, nodes.Const) and stmt.value.value is None)
        ):
            continue
        if isinstance(stmt, nodes.Raise):
            exc = stmt.exc
            if isinstance(exc, nodes.Call):
                exc = exc.func
            if isinstance(exc, nodes.Name) and exc.name == "NotImplementedError":
                continue
        return False
    return True


def _self_call_target(call: nodes.Call) -> str | None:
    """Return the entity method a ``self.<x>(...)`` call ultimately invokes.

    Resolves ``self.<method>(...)`` directly, and unwraps the executor pattern
    ``self.hass.async_add_executor_job(self.<method>, ...)`` /
    ``... ft.partial(self.<method>, ...)`` to the wrapped sync method.
    """
    callee = call.func
    if not isinstance(callee, nodes.Attribute):
        return None
    attrname: str
    if callee.attrname == "async_add_executor_job" and call.args:
        arg = call.args[0]
        if isinstance(arg, nodes.Call):  # ft.partial(self.method, ...)
            arg = arg.args[0] if arg.args else arg
        if (
            isinstance(arg, nodes.Attribute)
            and isinstance(arg.expr, nodes.Name)
            and arg.expr.name == "self"
        ):
            attrname = arg.attrname
            return attrname
        return None
    if isinstance(callee.expr, nodes.Name) and callee.expr.name == "self":
        attrname = callee.attrname
        return attrname
    return None


def _is_guard(stmt: nodes.NodeNG) -> bool:
    """Return True for a statement that only validates (never provides behavior).

    Guards are private-helper calls (``self._valid_mode_or_raise(...)``) and
    ``if ...: raise`` clauses. They may precede a delegation without changing
    which entity method backs the service.
    """
    if isinstance(stmt, nodes.Expr) and isinstance(stmt.value, nodes.Call):
        target = _self_call_target(stmt.value)
        return target is not None and target.startswith("_")
    if isinstance(stmt, nodes.If):
        return not stmt.orelse and all(isinstance(s, nodes.Raise) for s in stmt.body)
    return False


def _single_delegation(func: nodes.FunctionDef) -> str | None:
    """Return the single method *func* delegates to, or None.

    ``None`` means either no delegation or -- crucially -- *multiple*
    behavioral branches (a real base implementation with fallbacks, e.g.
    climate's ``async_turn_on``), which must not be treated as an
    unimplemented stub.
    """
    body = list(func.body)
    if (
        body
        and isinstance(body[0], nodes.Expr)
        and isinstance(body[0].value, nodes.Const)
    ):
        body = body[1:]
    behavior = [stmt for stmt in body if not _is_guard(stmt)]
    if len(behavior) != 1:
        return None
    stmt = behavior[0]
    if isinstance(stmt, (nodes.Return, nodes.Expr)):
        value = stmt.value
    else:
        return None
    if isinstance(value, nodes.Await):
        value = value.value
    if isinstance(value, nodes.Call):
        return _self_call_target(value)
    return None


def _base_methods(module: nodes.Module, pkg: str) -> dict[str, nodes.FunctionDef]:
    """Map method name -> FunctionDef for the platform's base entity classes.

    Base entity classes may live in a submodule (e.g. ``valve/entity.py``) and
    be re-exported from the package ``__init__``. We follow every public name
    the package exposes, keep the ones that resolve to an ``Entity`` subclass,
    and collect their methods (plus inherited methods defined within the same
    platform package). The most-derived definition wins.
    """
    bases: list[nodes.ClassDef] = []
    seen: set[str] = set()
    for name in list(module.globals):
        try:
            inferred = module.igetattr(name)
        except astroid.AstroidError:
            continue
        for value in inferred:
            if (
                isinstance(value, nodes.ClassDef)
                and value.qname() not in seen
                and inherits_from_entity(value)
            ):
                seen.add(value.qname())
                bases.append(value)

    pkg_dot = f"{pkg}."
    methods: dict[str, nodes.FunctionDef] = {}
    for base in bases:
        for klass in (base, *safe_ancestors(base)):
            module_name = klass.root().name
            if module_name != pkg and not module_name.startswith(pkg_dot):
                continue
            for item in klass.body:
                if isinstance(item, nodes.FunctionDef) and item.name not in methods:
                    methods[item.name] = item
    return methods


def _resolve_unit(
    name: str,
    base_methods: dict[str, nodes.FunctionDef],
    seen: frozenset[str] = frozenset(),
) -> frozenset[str] | None:
    """Resolve a method name to the abstract stub an integration must override.

    A "unit" is the sync/async method pair (``open_cover`` / ``async_open_cover``).
    Returns the acceptable override names, or ``None`` when the base already
    provides a working implementation (real body with fallbacks) or the chain
    can't be proven.
    """
    candidates = _candidate_methods(name)
    if candidates & seen:  # guard against delegation cycles
        return None
    seen = seen | candidates

    async_name = name if name.startswith("async_") else f"async_{name}"
    sync_name = name.removeprefix("async_")
    afunc = base_methods.get(async_name)
    sfunc = base_methods.get(sync_name)

    if afunc is None and sfunc is None:
        return None

    sync_is_stub = sfunc is not None and _is_trivial_body(sfunc)
    async_is_stub = afunc is not None and _is_trivial_body(afunc)
    # The async form is a plain executor wrapper around its own sync stub.
    async_wraps_sync = afunc is not None and _single_delegation(afunc) == sync_name

    if async_is_stub or (sync_is_stub and (afunc is None or async_wraps_sync)):
        return candidates

    # A base dispatcher (e.g. async_handle_open_service) that forwards to a
    # single other entity method -- follow it. Real implementations with
    # fallback branches yield no single delegation and stop here (not required).
    if afunc is not None:
        target = _single_delegation(afunc)
        if target and target not in candidates:
            return _resolve_unit(target, base_methods, seen)
    return None


def _resolve_requirement(
    func_arg: nodes.NodeNG,
    base_methods: dict[str, nodes.FunctionDef],
) -> frozenset[str] | None:
    """Resolve the entity method(s) backing a service handler argument."""
    if not (isinstance(func_arg, nodes.Const) and isinstance(func_arg.value, str)):
        # Handler is a module-level function or callable; can't statically
        # tie it to a required entity method.
        return None
    return _resolve_unit(func_arg.value, base_methods)


@cache
def _platform_feature_map(platform: str) -> dict[str, frozenset[str]]:
    """Map ``FEATURE_FLAG_NAME -> {acceptable method names}`` for a platform.

    Derived from the platform's ``async_register_entity_service`` calls.
    """
    try:
        module = MANAGER.ast_from_module_name(f"{_COMPONENTS_ROOT}.{platform}")
    except astroid.AstroidError:
        return {}

    base_methods = _base_methods(module, f"{_COMPONENTS_ROOT}.{platform}")
    result: dict[str, frozenset[str]] = {}

    for call in module.nodes_of_class(nodes.Call):
        callee = call.func
        if not (isinstance(callee, nodes.Attribute) and callee.attrname == _REGISTER):
            continue
        if len(call.args) < 4:
            continue
        flag = _single_flag_name(call.args[3])
        if flag is None or flag in result:
            continue
        methods = _resolve_requirement(call.args[2], base_methods)
        if methods:
            result[flag] = methods
    return result


def _single_flag_name(node: nodes.NodeNG) -> str | None:
    """Return the flag name if *node* is ``[XEntityFeature.FLAG]``, else None."""
    if not isinstance(node, nodes.List) or len(node.elts) != 1:
        return None
    return _flag_attr_name(node.elts[0])


def _flag_attr_name(node: nodes.NodeNG) -> str | None:
    """Return ``FLAG`` from an ``XEntityFeature.FLAG`` attribute node."""
    if isinstance(node, nodes.Attribute):
        owner = node.expr
        owner_name = (
            owner.name
            if isinstance(owner, nodes.Name)
            else owner.attrname
            if isinstance(owner, nodes.Attribute)
            else ""
        )
        if owner_name.endswith("EntityFeature"):
            attrname: str = node.attrname
            return attrname
    return None


def _extract_flags(node: nodes.NodeNG) -> set[str] | None:
    """Extract the set of flag names from a static feature expression.

    Returns ``None`` when the expression is not a pure combination of feature
    flags (i.e. dynamic / unknown), which signals the caller to skip.
    """
    if (flag := _flag_attr_name(node)) is not None:
        return {flag}
    if isinstance(node, nodes.BinOp) and node.op == "|":
        left = _extract_flags(node.left)
        right = _extract_flags(node.right)
        if left is None or right is None:
            return None
        return left | right
    # ``XEntityFeature(0)``, ``XEntityFeature()`` or literal ``0`` -> no
    # features (valid, empty). Any other call is a computed value -> unknown.
    if isinstance(node, nodes.Const) and node.value == 0:
        return set()
    if isinstance(node, nodes.Call):
        callee = node.func
        callee_name = (
            callee.name
            if isinstance(callee, nodes.Name)
            else callee.attrname
            if isinstance(callee, nodes.Attribute)
            else ""
        )
        if callee_name.endswith("EntityFeature") and (
            not node.args
            or (
                len(node.args) == 1
                and isinstance(node.args[0], nodes.Const)
                and node.args[0].value == 0
            )
        ):
            return set()
    return None


def _declared_flags(class_node: nodes.ClassDef) -> set[str] | None:
    """Return statically declared supported-feature flags for a class.

    Considers class-body ``_attr_supported_features = ...`` and plain
    ``self._attr_supported_features = ...`` assignments in the class' own
    methods. Returns ``None`` if any assignment is dynamic/uncertain (augmented
    assignment, non-literal value, or a ``supported_features`` property), so the
    class is skipped rather than guessed.
    """
    found = False
    flags: set[str] = set()

    def consume(value: nodes.NodeNG) -> bool:
        nonlocal found
        extracted = _extract_flags(value)
        if extracted is None:
            return False
        found = True
        flags.update(extracted)
        return True

    for node in class_node.body:
        # A supported_features property means the value is computed dynamically.
        if isinstance(node, nodes.FunctionDef) and node.name == "supported_features":
            return None
        if isinstance(node, (nodes.Assign, nodes.AnnAssign)):
            targets = node.targets if isinstance(node, nodes.Assign) else [node.target]
            if any(
                isinstance(t, nodes.AssignName) and t.name == _ATTR for t in targets
            ):
                if node.value is None or not consume(node.value):
                    return None

    for assign in class_node.nodes_of_class((nodes.Assign, nodes.AugAssign)):
        target = (
            assign.targets[0] if isinstance(assign, nodes.Assign) else assign.target
        )
        if not (
            isinstance(target, nodes.AssignAttr)
            and target.attrname == _ATTR
            and isinstance(target.expr, nodes.Name)
            and target.expr.name == "self"
        ):
            continue
        if isinstance(assign, nodes.AugAssign) or not consume(assign.value):
            return None

    return flags if found else None


def _is_implemented(
    class_node: nodes.ClassDef, candidates: frozenset[str], platform: str
) -> bool:
    """Return True if any candidate method is defined outside the platform base."""
    base_module = f"{_COMPONENTS_ROOT}.{platform}"
    for klass in (class_node, *safe_ancestors(class_node)):
        module_name = klass.root().name
        if module_name == base_module or module_name.startswith(f"{base_module}."):
            continue
        for name in candidates:
            defs = klass.locals.get(name)
            if defs and any(isinstance(d, nodes.FunctionDef) for d in defs):
                return True
    return False


class HassEnforceSupportedFeaturesChecker(BaseChecker):
    """Checker: declared supported features must be implemented."""

    name = "home_assistant_supported_features"
    priority = -1
    msgs = {
        "W7428": (
            "Entity declares supported feature %s but does not implement %s",
            "home-assistant-missing-feature-implementation",
            "Used when an entity's supported_features advertises a flag whose "
            "backing method is not implemented, so the corresponding service "
            "would raise NotImplementedError or silently do nothing.",
        ),
    }
    options = ()

    def __init__(self, linter: PyLinter) -> None:
        """Initialize the checker."""
        super().__init__(linter)
        self._same_module_ancestors: set[str] = set()

    def visit_module(self, node: nodes.Module) -> None:
        """Record classes used as same-module bases so they can be exempted."""
        self._same_module_ancestors = collect_same_module_ancestor_qnames(node)

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Check an entity class' declared features against implementations."""
        if node.qname() in self._same_module_ancestors:
            return
        if not inherits_from_entity(node):
            return
        platform = _platform_of(node)
        if platform is None:
            return
        feature_map = _platform_feature_map(platform)
        if not feature_map:
            return
        declared = _declared_flags(node)
        if not declared:
            return
        for flag in sorted(declared):
            candidates = feature_map.get(flag)
            if candidates and not _is_implemented(node, candidates, platform):
                self.add_message(
                    "home-assistant-missing-feature-implementation",
                    node=node,
                    args=(flag, " / ".join(sorted(candidates))),
                )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceSupportedFeaturesChecker(linter))
