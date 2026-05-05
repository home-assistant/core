"""Plugin for detecting direct coordinator instantiation in integration tests.

Coordinators should not be instantiated directly in tests. Instead, the
behavior of a coordinator should be exercised indirectly through the entities
it backs, the state machine, the device registry, and the entity registry.
When the coordinator works correctly, the entities reflect that, and the
inverse holds as well -- if the entities behave correctly, the coordinator
behaves correctly.

This checker flags any test module under ``tests/components/**/test_*.py``
that directly instantiates a class which (transitively) inherits from
``homeassistant.helpers.update_coordinator.DataUpdateCoordinator``.
"""

from __future__ import annotations

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

_COORDINATOR_BASE_QNAMES: frozenset[str] = frozenset(
    {
        "homeassistant.helpers.update_coordinator.DataUpdateCoordinator",
        "homeassistant.helpers.update_coordinator.TimestampDataUpdateCoordinator",
    }
)


class HassEnforceNoCoordinatorInstantiationInTestsChecker(BaseChecker):
    """Checker that flags direct coordinator instantiation inside tests."""

    name = "hass_enforce_no_coordinator_instantiation_in_tests"
    priority = -1
    msgs = {
        "W7461": (
            "Coordinator '%s' should not be instantiated directly in tests; "
            "test the coordinator's behavior indirectly through entities, the "
            "state machine, and registries",
            "hass-no-coordinator-instantiation-in-tests",
            "Used when a test under tests/components/ directly instantiates a "
            "DataUpdateCoordinator subclass. Coordinator behavior should be "
            "verified through the entities it backs rather than by exercising "
            "the coordinator instance directly.",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check whether this call instantiates a coordinator subclass."""
        root_name = node.root().name
        if not _is_integration_test_module(root_name):
            return

        inferred = _safe_infer(node.func)
        if not isinstance(inferred, nodes.ClassDef):
            return

        if not _inherits_from_coordinator(inferred):
            return

        self.add_message(
            "hass-no-coordinator-instantiation-in-tests",
            node=node,
            args=(inferred.name,),
        )


def _is_integration_test_module(root_name: str) -> bool:
    """Return True if ``root_name`` belongs to an integration test module."""
    if not root_name.startswith("tests.components."):
        return False
    parts = root_name.split(".")
    # Expect ``tests.components.<integration>.test_<name>[...]``
    return len(parts) >= 4 and parts[-1].startswith("test_")


def _safe_infer(node: nodes.NodeNG) -> nodes.NodeNG | None:
    """Best-effort inference that swallows astroid errors."""
    try:
        inferred = next(node.infer(), None)
    except astroid.InferenceError:
        return None
    if inferred is astroid.Uninferable:
        return None
    return inferred


def _inherits_from_coordinator(class_def: nodes.ClassDef) -> bool:
    """Return True if ``class_def`` inherits from a coordinator base."""
    if class_def.qname() in _COORDINATOR_BASE_QNAMES:
        return True
    try:
        ancestors = class_def.ancestors()
    except astroid.MroError:
        return False
    return any(ancestor.qname() in _COORDINATOR_BASE_QNAMES for ancestor in ancestors)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceNoCoordinatorInstantiationInTestsChecker(linter))
