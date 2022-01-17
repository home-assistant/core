"""Plugin for constructor definitions."""
import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker
from pylint.lint import PyLinter


class HassTypeHintChecker(BaseChecker):  # type: ignore[misc]
    """Checker for setup type hints."""

    __implements__ = IAstroidChecker

    name = "hass_enforce_type_hints"
    priority = -1
    msgs = {
        "W0012": (
            "First argument should be of type HomeAssistant",
            "hass-enforce-type-hints-hass",
            "Used when setup has some arguments typed but first isn't HomeAssistant",
        ),
        "W0013": (
            "Second argument should be of type ConfigType",
            "hass-enforce-type-hints-config-type",
            "Used when setup has some arguments typed but first isn't ConfigType",
        ),
        "W0014": (
            "Second argument should be of type ConfigEntry",
            "hass-enforce-type-hints-config-entry",
            "Used when setup has some arguments typed but first isn't ConfigEntry",
        ),
        "W0015": (
            "Return type should be of type bool",
            "hass-enforce-type-hints-return-bool",
            "Used when setup has some arguments typed but doesn't return bool",
        ),
        "W0016": (
            "First argument should be of type HomeAssistant",
            "hass-enforce-type-hints-return-none",
            "Used when setup has some arguments typed but doesn't return None",
        ),
    }
    options = ()

    def visit_functiondef(self, node: astroid.FunctionDef) -> None:
        """Called when a FunctionDef node is visited."""
        if node.is_method() or node.name not in [
            "setup",
            "async_setup",
            "async_setup_entry",
            "async_remove_entry",
            "async_unload_entry",
            "async_migrate_entry",
        ]:
            return

        # Check that all arguments are annotated.
        # The first argument is "self".
        args = node.args
        annotations = (
            args.posonlyargs_annotations
            + args.annotations
            + args.kwonlyargs_annotations
        )
        if args.vararg is not None:
            annotations.append(args.varargannotation)
        if args.kwarg is not None:
            annotations.append(args.kwargannotation)
        if not [annotation for annotation in annotations if annotation is not None]:
            return

        print(annotations)

        # Check that the first argument is "HomeAssistant".
        if (
            not isinstance(annotations[0], astroid.Name)
            or annotations[0].name != "HomeAssistant"
        ):
            self.add_message("hass-enforce-type-hints-hass", node=node)
        # Check that the second argument is "ConfigType" or "ConfigEntry".
        if node.name in ["setup", "async_setup"]:
            if (
                not isinstance(annotations[1], astroid.Name)
                or annotations[1].name != "ConfigType"
            ):
                self.add_message("hass-enforce-type-hints-config-type", node=node)
        else:
            if (
                not isinstance(annotations[1], astroid.Name)
                or annotations[1].name != "ConfigEntry"
            ):
                self.add_message("hass-enforce-type-hints-config-entry", node=node)
        # Check that return type is specified and it is "None".
        if node.name == "async_remove_entry":
            if (
                not isinstance(node.returns, astroid.Const)
                or node.returns.value is not None
            ):
                self.add_message("hass-enforce-type-hints-return-none", node=node)
        else:
            if (
                not isinstance(node.returns, astroid.Name)
                or node.returns.name != "bool"
            ):
                self.add_message("hass-enforce-type-hints-return-bool", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassConstructorFormatChecker(linter))
