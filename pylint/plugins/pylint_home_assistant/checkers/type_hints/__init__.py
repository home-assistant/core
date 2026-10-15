"""Checker to enforce type hints on specific functions."""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import ANY_PLATFORM, ENTITY_COMPONENTS
from pylint_home_assistant.helpers.module_info import get_module_platform

from .const import (
    _CLASS_MATCH,
    _COMMON_ARGUMENTS,
    _FORCE_ANNOTATION_PLATFORMS,
    _FUNCTION_MATCH,
    _INHERITANCE_MATCH,
    _METHOD_MATCH,
    _TEST_FIXTURES,
)
from .models import ClassTypeHintMatch, TypeHintMatch
from .validators import (
    get_all_annotations,
    get_named_annotation,
    has_valid_annotations,
    is_valid_return_type,
    is_valid_type,
)


class HassTypeHintChecker(BaseChecker):
    """Checker for setup type hints."""

    name = "home_assistant_enforce_type_hints"
    priority = -1
    msgs = {
        "E7402": (
            "Argument %s should be of type %s in %s",
            "home-assistant-argument-type",
            "Used when method argument type is incorrect",
        ),
        "E7403": (
            "Return type should be %s in %s",
            "home-assistant-return-type",
            "Used when method return type is incorrect",
        ),
        "R7401": (
            "Argument %s is of type %s and could be moved to "
            "`@pytest.mark.usefixtures` decorator in %s",
            "home-assistant-consider-usefixtures-decorator",
            "Used when an argument type is None and could be a fixture",
        ),
    }
    options = (
        (
            "ignore-missing-annotations",
            {
                "default": False,
                "type": "yn",
                "metavar": "<y or n>",
                "help": "Set to ``no`` if you wish to check functions that do not "
                "have any type hints.",
            },
        ),
    )

    _class_matchers: list[ClassTypeHintMatch]
    _function_matchers: list[TypeHintMatch]
    _module_node: nodes.Module
    _module_platform: str | None
    _in_test_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Populate matchers for a Module node."""
        self._class_matchers = []
        self._function_matchers = []
        self._module_node = node
        self._module_platform = get_module_platform(node.name)
        self._in_test_module = node.name.startswith("tests.")

        if self._in_test_module or self._module_platform is None:
            return

        if self._module_platform in ENTITY_COMPONENTS:
            self._function_matchers.extend(_FUNCTION_MATCH[ANY_PLATFORM])

        if function_matches := _FUNCTION_MATCH.get(self._module_platform):
            self._function_matchers.extend(function_matches)

        if class_matches := _CLASS_MATCH.get(self._module_platform):
            self._class_matchers.extend(class_matches)

        if property_matches := _INHERITANCE_MATCH.get(self._module_platform):
            self._class_matchers.extend(property_matches)

        self._class_matchers.reverse()

    def _ignore_function_match(
        self,
        node: nodes.FunctionDef,
        annotations: list[nodes.NodeNG | None],
        match: TypeHintMatch,
    ) -> bool:
        """Check if we can skip the function validation."""
        return (
            # test modules are excluded from ignore_missing_annotations
            not self._in_test_module
            # some modules have checks forced
            and self._module_platform not in _FORCE_ANNOTATION_PLATFORMS
            # some matches have checks forced
            and not match.mandatory
            # other modules are only checked ignore_missing_annotations
            and self.linter.config.ignore_missing_annotations
            and node.returns is None
            and not has_valid_annotations(annotations)
        )

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Apply relevant type hint checks on a ClassDef node."""
        ancestor: nodes.ClassDef
        checked_class_methods: set[str] = set()
        ancestors = list(node.ancestors())  # cache result for inside loop
        for class_matcher in self._class_matchers:
            skip_matcher = False
            if exclude_base_classes := class_matcher.exclude_base_classes:
                for ancestor in ancestors:
                    if ancestor.name in exclude_base_classes:
                        skip_matcher = True
                        break
            if skip_matcher:
                continue
            for ancestor in ancestors:
                if ancestor.name == class_matcher.base_class:
                    self._visit_class_functions(
                        node, class_matcher.matches, checked_class_methods
                    )

    def _visit_class_functions(
        self,
        node: nodes.ClassDef,
        matches: list[TypeHintMatch],
        checked_class_methods: set[str],
    ) -> None:
        cached_methods: list[nodes.FunctionDef] = list(node.mymethods())
        for match in matches:
            for function_node in cached_methods:
                if (
                    function_node.name in checked_class_methods
                    or not match.need_to_check_function(function_node)
                ):
                    continue

                annotations = get_all_annotations(function_node)
                if self._ignore_function_match(function_node, annotations, match):
                    continue

                self._check_function(function_node, match, annotations)
                checked_class_methods.add(function_node.name)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Apply relevant type hint checks on a FunctionDef node."""
        annotations = get_all_annotations(node)

        # Check method or function matchers.
        if node.is_method():
            matchers = _METHOD_MATCH
        else:
            if self._in_test_module and node.parent is self._module_node:
                if node.name.startswith("test_"):
                    self._check_test_function(node, False)
                    return
                if (decoratornames := node.decoratornames()) and (
                    # `@pytest.fixture`
                    "_pytest.fixtures.fixture" in decoratornames
                    # `@pytest.fixture(...)`
                    or "_pytest.fixtures.FixtureFunctionMarker" in decoratornames
                ):
                    self._check_test_function(node, True)
                    return
            matchers = self._function_matchers

        # Check that common arguments are correctly typed.
        if not self.linter.config.ignore_missing_annotations:
            for arg_name, expected_type in _COMMON_ARGUMENTS.items():
                arg_node, annotation = get_named_annotation(node, arg_name)
                if arg_node and not is_valid_type(expected_type, annotation):
                    self.add_message(
                        "home-assistant-argument-type",
                        node=arg_node,
                        args=(arg_name, expected_type, node.name),
                    )

        for match in matchers:
            if not match.need_to_check_function(node):
                continue
            self._check_function(node, match, annotations)

    visit_asyncfunctiondef = visit_functiondef

    def _check_function(
        self,
        node: nodes.FunctionDef,
        match: TypeHintMatch,
        annotations: list[nodes.NodeNG | None],
    ) -> None:
        if self._ignore_function_match(node, annotations, match):
            return
        # Check that all positional arguments are correctly annotated.
        if match.arg_types:
            for key, expected_type in match.arg_types.items():
                if key > len(node.args.args) - 1:
                    # The number of arguments is less than expected
                    self.add_message(
                        "home-assistant-argument-type",
                        node=node,
                        args=(key + 1, expected_type, node.name),
                    )
                    continue
                if node.args.args[key].name in _COMMON_ARGUMENTS:
                    # It has already been checked, avoid double-message
                    continue
                if not is_valid_type(expected_type, annotations[key]):
                    self.add_message(
                        "home-assistant-argument-type",
                        node=node.args.args[key],
                        args=(key + 1, expected_type, node.name),
                    )

        # Check that all keyword arguments are correctly annotated.
        if match.named_arg_types is not None:
            for arg_name, expected_type in match.named_arg_types.items():
                if arg_name in _COMMON_ARGUMENTS:
                    # It has already been checked, avoid double-message
                    continue
                arg_node, annotation = get_named_annotation(node, arg_name)
                if arg_node and not is_valid_type(expected_type, annotation):
                    self.add_message(
                        "home-assistant-argument-type",
                        node=arg_node,
                        args=(arg_name, expected_type, node.name),
                    )

        # Check that kwargs is correctly annotated.
        if match.kwargs_type and not is_valid_type(
            match.kwargs_type, node.args.kwargannotation
        ):
            self.add_message(
                "home-assistant-argument-type",
                node=node,
                args=(node.args.kwarg, match.kwargs_type, node.name),
            )

        # Check the return type.
        if not is_valid_return_type(match, node.returns):
            self.add_message(
                "home-assistant-return-type",
                node=node,
                args=(match.return_type or "None", node.name),
            )

    def _check_test_function(self, node: nodes.FunctionDef, is_fixture: bool) -> None:
        # Check the return type, should always be `None` for test_*** functions.
        if not is_fixture and not is_valid_type(None, node.returns, True):
            self.add_message(
                "home-assistant-return-type",
                node=node,
                args=("None", node.name),
            )
        # Check that all positional arguments are correctly annotated.
        for arg_name, expected_type in _TEST_FIXTURES.items():
            arg_node, annotation = get_named_annotation(node, arg_name)
            if arg_node and expected_type == "None" and not is_fixture:
                self.add_message(
                    "home-assistant-consider-usefixtures-decorator",
                    node=arg_node,
                    args=(arg_name, expected_type, node.name),
                )
            if arg_node and not is_valid_type(expected_type, annotation):
                self.add_message(
                    "home-assistant-argument-type",
                    node=arg_node,
                    args=(arg_name, expected_type, node.name),
                )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassTypeHintChecker(linter))
