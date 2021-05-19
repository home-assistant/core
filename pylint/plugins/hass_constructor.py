from astroid.node_classes import Const
from astroid.nodes import ClassDef
from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker


class HassConstructorFormatChecker(BaseChecker):
    """Check that __init__ return type is present."""

    __implements__ = IAstroidChecker

    name = "hass_constructor"
    priority = -1
    msgs = {
        "W0006": (
            '__init__ should have explicit return type "None"',
            "hass-constructor-return",
            "Used when __init__ has all arguments typed "
            "but doesn't have return type declared",
        ),
    }
    options = ()

    def visit_functiondef(self, node):
        """Called when a :class:`.astroid.node_classes.FunctionDef` node is visited.
        See :mod:`astroid` for the description of available nodes.
        :param node: The node to check.
        :type node: astroid.node_classes.FunctionDef
        """
        if not node.is_method() or node.name != "__init__":
            return

        # Check that all arguments are annotated.
        # The first argument is "self".
        annotations = (
            node.args.posonlyargs_annotations
            + node.args.annotations
            + node.args.kwonlyargs_annotations
        )[1:]
        if not annotations or any(hint is None for hint in annotations):
            return

        # Check that return type is specified and it is "None".
        if not isinstance(node.returns, Const) or node.returns.value != None:
            self.add_message("hass-constructor-return", node=node)


def register(linter):
    """This required method auto registers the checker.
    :param linter: The linter to register the checker to.
    :type linter: pylint.lint.PyLinter
    """
    linter.register_checker(HassConstructorFormatChecker(linter))
