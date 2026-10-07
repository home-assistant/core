"""Checker for entity device info set to a plain dict.

``_attr_device_info`` and the ``device_info`` property of an entity should
use the ``DeviceInfo`` object, as that is type-safe, instead of a dict
literal or ``dict(...)`` call.

``W7439`` (``home-assistant-device-info-dict``)
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.entity_class import inherits_from_entity
from pylint_home_assistant.helpers.module_info import is_integration_module


def _is_dict(node: nodes.NodeNG | None) -> bool:
    """Check if a node is a dict literal or a ``dict(...)`` call."""
    match node:
        case nodes.Dict():
            return True
        case nodes.Call(func=nodes.Name(name="dict")):
            return True
    return False


def _is_device_info_target(node: nodes.NodeNG) -> bool:
    """Check if a node is ``self._attr_device_info`` or ``_attr_device_info``."""
    match node:
        case nodes.AssignName(name="_attr_device_info"):
            return True
        case nodes.AssignAttr(attrname="_attr_device_info"):
            return True
    return False


class DeviceInfoDictChecker(BaseChecker):
    """Checker for ``_attr_device_info`` set to a plain dict."""

    name = "home_assistant_device_info_dict"
    priority = -1
    msgs = {
        "W7439": (
            "Use DeviceInfo instead of a dict for entity device info",
            "home-assistant-device-info-dict",
            "Used when _attr_device_info is set to a dict, or when the "
            "device_info property of an entity returns a dict. Use the "
            "DeviceInfo object instead, as it is type-safe.",
        ),
    }
    options = ()

    _in_integration: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration module."""
        self._in_integration = is_integration_module(node.name)

    def visit_assign(self, node: nodes.Assign) -> None:
        """Check assignments of a dict to ``_attr_device_info``."""
        if not self._in_integration:
            return
        if not _is_dict(node.value):
            return
        if not any(_is_device_info_target(target) for target in node.targets):
            return
        self.add_message("home-assistant-device-info-dict", node=node.value)

    def visit_annassign(self, node: nodes.AnnAssign) -> None:
        """Check annotated assignments of a dict to ``_attr_device_info``."""
        if not self._in_integration:
            return
        if not _is_dict(node.value) or not _is_device_info_target(node.target):
            return
        self.add_message("home-assistant-device-info-dict", node=node.value)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check dicts returned from an entity's ``device_info`` property."""
        if not self._in_integration or node.name != "device_info":
            return
        class_node = node.parent
        if not isinstance(class_node, nodes.ClassDef) or not inherits_from_entity(
            class_node
        ):
            return
        for return_node in node.nodes_of_class(nodes.Return):
            if return_node.frame() is node and _is_dict(return_node.value):
                self.add_message("home-assistant-device-info-dict", node=return_node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(DeviceInfoDictChecker(linter))
