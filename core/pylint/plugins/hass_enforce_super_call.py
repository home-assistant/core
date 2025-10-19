"""Plugin for checking super calls."""

from __future__ import annotations

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.interfaces import INFERENCE
from pylint.lint import PyLinter


METHODS = {
    "async_added_to_hass",
}


def _contains_super_call(node: nodes.NodeNG, method_name: str) -> bool:
    """
    Recursively search `node` and its descendants for a call of the form:
      super().<method_name>(...)
    Returns True if found, False otherwise.
    """
    # If this node is a Call node, check whether it matches super().<method_name>(...)
    if isinstance(node, nodes.Call):
        func = getattr(node, "func", None)
        if isinstance(func, nodes.Attribute):
            # attrname is the method being called (e.g., "async_added_to_hass")
            attrname = getattr(func, "attrname", None)
            expr = getattr(func, "expr", None)
            if attrname == method_name and isinstance(expr, nodes.Call):
                inner_func = getattr(expr, "func", None)
                # Typical modern form: super().method(...)
                if isinstance(inner_func, nodes.Name) and inner_func.name == "super":
                    return True
                # Also handle super(SomeClass, self).method(...) (inner_func still a Name "super")
                # The check above already covers it because inner_func.name == "super"
    # Recursively check children nodes
    for child in node.get_children():
        try:
            if _contains_super_call(child, method_name):
                return True
        except Exception:
            # Defensive: if some unexpected node shape throws, ignore that branch
            continue

    return False


class HassEnforceSuperCallChecker(BaseChecker):
    """Checker for super calls."""

    name = "hass_enforce_super_call"
    priority = -1
    msgs = {
        "W7441": (
            "Missing call to: super().%s",
            "hass-missing-super-call",
            "Used when method should call its parent implementation.",
        ),
    }
    options = ()

    def visit_functiondef(
        self, node: nodes.FunctionDef | nodes.AsyncFunctionDef
    ) -> None:
        """Check for super calls in method body."""
        if node.name not in METHODS:
            return

        assert node.parent
        parent = node.parent.frame()
        if not isinstance(parent, nodes.ClassDef):
            return

        # ---- Improved detection: search whole method body recursively ----
        for child in node.body:
            if _contains_super_call(child, node.name):
                # Found a super().<method_name>(...) somewhere — no warning
                return

        # Check for non-empty base implementation
        found_base_implementation = False
        for base in parent.ancestors():
            for method in base.mymethods():
                if method.name != node.name:
                    continue
                if method.body and not (
                    len(method.body) == 1 and isinstance(method.body[0], nodes.Pass)
                ):
                    found_base_implementation = True
                break

            if found_base_implementation:
                self.add_message(
                    "hass-missing-super-call",
                    node=node,
                    args=(node.name,),
                    confidence=INFERENCE,
                )
                break

    visit_asyncfunctiondef = visit_functiondef


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceSuperCallChecker(linter))
