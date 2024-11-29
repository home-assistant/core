"""Enforce that the integration sets has_entity_name=True on entities.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/has-entity-name
"""

import ast
from dataclasses import dataclass

import pytest

from script.hassfest.model import Integration


@dataclass
class ClassInfo:
    """Class info container."""

    name: str
    found: bool
    bases: list["ClassInfo"]


class ClassVarVisitor(ast.NodeVisitor):
    """Visitor to report classes that do not define given classvar in their hierarchy."""

    def __init__(self, var):
        """Initialize."""
        self._wanted_classvar = var
        self._classes = {}

    def visit_ClassDef(self, node):
        """Visit classes."""
        if node.name in self._classes:
            return

        def _get_class_name(node):
            if isinstance(node, ast.Name):
                return node.id

            # generics
            if isinstance(node, ast.Subscript):
                return node.value.id

            # enums
            if isinstance(node, ast.Attribute):
                return node.value.id

            raise Exception("unexpected node type")  # noqa: TRY002

        self._classes[node.name] = ClassInfo(name=node.name, found=False, bases=[])
        self._classes[node.name].bases = [
            _get_class_name(parent) for parent in node.bases
        ]

        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue

            # TODO: no unpacking, but `entity_name, foobar = True, 1 unlikely wanted
            assert len(stmt.targets) == 1
            var = stmt.targets[0]

            if var.id == self._wanted_classvar:
                self._classes[node.name].found = stmt.value.value
                break

    def result(self) -> list[str]:
        """Return results."""

        def _is_entity_class(info):
            # TODO: check for platform base class names to avoid false positives?
            return info.name.endswith("Entity") or any(
                name for name in info.bases if name.endswith("Entity")
            )

        def _has_wanted_variable_in_hierarchy(cls_name):
            """Return True if the class or its bases assign the wanted as True."""
            if cls_name not in self._classes:
                return False

            return self._classes[cls_name].found or any(
                _has_wanted_variable_in_hierarchy(name)
                for name in self._classes[cls_name].bases
            )

        entity_classes = {
            cls: info for cls, info in self._classes.items() if _is_entity_class(info)
        }

        # We do not care about the mro for now, return results that do not have our wanted classvar anywhere
        return [
            cls.name
            for cls in entity_classes.values()
            if not _has_wanted_variable_in_hierarchy(cls.name)
        ]


def validate(integration: Integration) -> list[str] | None:
    """Validate that the integration entities have has_entity_name=True."""

    wanted_variable = "_attr_has_entity_name"
    visitor = ClassVarVisitor(wanted_variable)

    python_files = integration.path.glob("*.py")
    for file in python_files:
        module = ast.parse(file.read_text())
        visitor.visit(module)

    if res := visitor.result():
        return [f"{cls} does not define {wanted_variable}" for cls in res]

    return None


VAR_MISSING = """\
class FooEntity:
    pass
"""

VAR_FALSE = """\
class FooEntity:
    _attr_has_entity_name = False
"""

VAR_TRUE = """\
class FooEntity:
    _attr_has_entity_name = True
"""

VAR_PARENT = """\
class Parent:
    _attr_has_entity_name = True
class FooEntity(Parent):
    pass
"""

VAR_DEEP = """\
class Parent2:
    _attr_has_entity_name = True
class Parent1(Parent2):
    pass
class FooEntity(Parent1):
    pass
"""

VAR_GENERIC = """\
class T:
    pass
class FooEntity(Generic[T]):
    _attr_has_entity_name = True
"""

VAR_GENERIC_MISSING = """\
class T:
    pass
class FooEntity(Generic[T]):
    pass
"""


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(VAR_MISSING, "FooEntity", id="missing"),
        pytest.param(VAR_FALSE, "FooEntity", id="false"),
        pytest.param(VAR_TRUE, [], id="true"),
        pytest.param(VAR_DEEP, [], id="deep in hierarchy"),
        pytest.param(VAR_GENERIC, [], id="inherits from generic"),
        pytest.param(VAR_GENERIC_MISSING, "FooEntity", id="generic missing"),
    ],
)
def tests(data, expected):
    """Tests for classvarvisitor."""
    parsed = ast.parse(data)
    v = ClassVarVisitor("_attr_has_entity_name")
    v.visit(parsed)
    if isinstance(expected, list):
        assert expected == v.result()
    else:
        assert expected in v.result()
