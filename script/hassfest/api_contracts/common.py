"""Index API declarations without importing integrations or optional dependencies."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from importlib.util import resolve_name
from pathlib import Path
import re
from typing import Any

from script.hassfest import ast_parse_module

PATH_PARAMETER = re.compile(r"\{([^}:]+)(?::[^}]+)?\}")

type Handler = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True, slots=True)
class IntegrationMetadata:
    """Maintained integration metadata used by both contracts."""

    name: str
    documentation: str
    group: str
    brand: str | None = None

    @property
    def description(self) -> str:
        """Return a useful display label when it adds information."""
        if self.brand and self.brand.casefold() not in self.name.casefold():
            return f"{self.name} ({self.brand})"
        return self.name


@dataclass(frozen=True, slots=True)
class Interface:
    """Metadata shared by machine interfaces."""

    name: str
    integration: str
    summary: str | None
    description: str | None


class SourceIndex:
    """Resolve the small subset of source needed by API declarations."""

    def __init__(self, root: Path) -> None:
        """Index Home Assistant modules without importing integrations."""
        self.root = root
        self.package = root / "homeassistant"
        self.trees: dict[str, ast.Module] = {}
        self.assignments: dict[tuple[str, str], ast.expr] = {}
        self.classes: dict[tuple[str, str], ast.ClassDef] = {}
        self.functions: dict[tuple[str, str], Handler] = {}
        self.imports: dict[tuple[str, str], tuple[str, str]] = {}

        for path in sorted(self.package.rglob("*.py")):
            try:
                tree = ast_parse_module(path)
            except SyntaxError, UnicodeDecodeError:
                continue

            module = ".".join(path.relative_to(root).with_suffix("").parts)
            self.trees[module] = tree

            # API declarations reference top-level symbols; nested definitions stay local.
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    self.classes[(module, node.name)] = node
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.functions[(module, node.name)] = node
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    self._index_assignment(module, node)
                elif isinstance(node, ast.ImportFrom):
                    imported_module = self._absolute_module(
                        module, node.module, node.level
                    )
                    for alias in node.names:
                        self.imports[(module, alias.asname or alias.name)] = (
                            imported_module,
                            alias.name,
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        local_name = alias.asname or alias.name.split(".")[0]
                        self.imports[(module, local_name)] = (alias.name, "")

    def _index_assignment(self, module: str, node: ast.Assign | ast.AnnAssign) -> None:
        """Index a simple assignment to a name."""
        value = node.value
        if value is None:
            return
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                self.assignments[(module, target.id)] = value

    @staticmethod
    def _absolute_module(current: str, imported: str | None, level: int) -> str:
        """Resolve a possibly relative import from an indexed module."""
        if level == 0:
            return imported or ""
        package = current.rpartition(".")[0]
        return resolve_name("." * level + (imported or ""), package)

    def module_key(self, module: str) -> str:
        """Return the indexed key for a module or package."""
        if module in self.trees:
            return module
        package = f"{module}.__init__"
        return package if package in self.trees else module

    def imported(self, module: str, name: str) -> tuple[str, str] | None:
        """Resolve an imported symbol to its source module and name."""
        if target := self.imports.get((module, name)):
            target_module, target_name = target
            return self.module_key(target_module), target_name
        return None

    def expression(
        self, module: str, node: ast.expr | None
    ) -> tuple[str, ast.expr] | None:
        """Resolve a name to its assigned expression."""
        if isinstance(node, ast.Name):
            if value := self.assignments.get((module, node.id)):
                return module, value
            if imported := self.imported(module, node.id):
                imported_module, imported_name = imported
                if value := self.assignments.get((imported_module, imported_name)):
                    return imported_module, value
        # Restrict dotted resolution to module.symbol; arbitrary attribute access is unsafe.
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if imported := self.imported(module, node.value.id):
                imported_module, imported_name = imported
                if imported_name:
                    package = imported_module.removesuffix(".__init__")
                    imported_module = self.module_key(f"{package}.{imported_name}")
                if value := self.assignments.get((imported_module, node.attr)):
                    return imported_module, value
        elif node is not None:
            return module, node
        return None

    def value(
        self,
        module: str,
        node: ast.expr | None,
        seen: set[tuple[str, str]] | None = None,
        local_assignments: dict[tuple[str, str], ast.expr] | None = None,
    ) -> Any:
        """Evaluate literal route metadata without executing integration code."""
        match node:
            case None:
                return None
            case ast.Constant() | ast.UnaryOp(op=ast.USub()):
                try:
                    return ast.literal_eval(node)
                except ValueError, TypeError:
                    return None
            case ast.List(elts=items) | ast.Tuple(elts=items) | ast.Set(elts=items):
                values = [
                    self.value(module, item, seen, local_assignments) for item in items
                ]
                return values if all(value is not None for value in values) else None
            case ast.BinOp(left=left_node, op=ast.Add(), right=right_node):
                left = self.value(module, left_node, seen, local_assignments)
                right = self.value(module, right_node, seen, local_assignments)
                return left + right if isinstance(left, type(right)) else None
            case ast.JoinedStr(values=parts):
                # Resolve only literal/imported substitutions; never evaluate expressions.
                result = ""
                for part in parts:
                    match part:
                        case ast.Constant(value=value):
                            result += str(value)
                        case ast.FormattedValue(value=value):
                            resolved = self.value(
                                module, value, seen, local_assignments
                            )
                            if resolved is None and isinstance(value, ast.Name):
                                resolved = "{" + value.id.lower() + "}"
                            if resolved is None:
                                return None
                            result += str(resolved)
                return result
            case ast.Name(id=name):
                key = (module, name)
                seen = set() if seen is None else seen
                if key in seen:
                    return None
                # Keep cycle detection local to this branch. Reusing the same constant in
                # a sibling expression is valid and must not look like recursion.
                seen = seen | {key}
                if value := (local_assignments or {}).get(key):
                    return self.value(module, value, seen, local_assignments)
                if value := self.assignments.get(key):
                    return self.value(module, value, seen, local_assignments)
                if imported := self.imported(module, name):
                    imported_module, imported_name = imported
                    return self.value(
                        imported_module,
                        ast.Name(id=imported_name),
                        seen,
                        local_assignments,
                    )

            case ast.Call(
                func=ast.Attribute(value=subject, attr="format"), keywords=keywords
            ):
                # Route templates use named fields; preserve unresolved path parameters.
                if isinstance(
                    template := self.value(module, subject, seen, local_assignments),
                    str,
                ):
                    values = {
                        keyword.arg: self.value(
                            module, keyword.value, seen, local_assignments
                        )
                        for keyword in keywords
                        if keyword.arg
                    }
                    for field in PATH_PARAMETER.findall(template):
                        values.setdefault(field, "{" + field + "}")
                    try:
                        return template.format(**values)
                    except KeyError, ValueError:
                        return None
        return None

    def class_target(self, module: str, node: ast.expr) -> tuple[str, str] | None:
        """Resolve a class base expression."""
        match node:
            case ast.Subscript(value=value):
                return self.class_target(module, value)
            case ast.Name(id=name):
                return self._class_symbol(module, name)
            case ast.Attribute(value=ast.Name(id=subject), attr=name):
                if imported := self.imported(module, subject):
                    imported_module, imported_name = imported
                    if not imported_name:
                        return self._class_symbol(imported_module, name)
                    package = imported_module.removesuffix(".__init__")
                    submodule = self.module_key(f"{package}.{imported_name}")
                    if submodule in self.trees:
                        return self._class_symbol(submodule, name)
        return None

    def function_target(self, module: str, node: ast.expr) -> tuple[str, str] | None:
        """Resolve a function expression to its indexed definition."""
        match node:
            case ast.Name(id=name):
                key = (self.module_key(module), name)
                if key in self.functions:
                    return key
                return self.imported(*key)
            case ast.Attribute(value=ast.Name(id=subject), attr=name):
                if imported := self.imported(module, subject):
                    imported_module, imported_name = imported
                    if imported_name:
                        package = imported_module.removesuffix(".__init__")
                        imported_module = self.module_key(f"{package}.{imported_name}")
                    return imported_module, name
        return None

    @staticmethod
    def source_url(module: str, node: ast.stmt | ast.expr) -> str:
        """Return the GitHub link for an indexed source definition."""
        path = module.replace(".", "/") + ".py"
        return f"https://github.com/home-assistant/core/blob/dev/{path}"

    def _class_symbol(
        self,
        module: str,
        name: str,
        seen: set[tuple[str, str]] | None = None,
    ) -> tuple[str, str]:
        """Follow re-exported class symbols to their definition."""
        key = (self.module_key(module), name)
        seen = set() if seen is None else seen
        if key in self.classes or key in seen:
            return key
        seen.add(key)
        if imported := self.imported(*key):
            return self._class_symbol(*imported, seen)
        return key


def source_description(
    index: SourceIndex, module: str, node: ast.stmt | ast.expr, description: str = ""
) -> str:
    """Link generated reference text to its production source."""
    link = f"[View source]({index.source_url(module, node)})"
    return f"{description}\n\n{link}" if description else link


def interface_metadata(
    index: SourceIndex,
    module: str,
    node: Handler,
    fallback: ast.ClassDef | None = None,
) -> tuple[str | None, str]:
    """Return a summary and source-linked description for an interface."""
    doc = ast.get_docstring(node) or (ast.get_docstring(fallback) if fallback else "")
    summary = doc.splitlines()[0] if doc else None
    detail = doc if doc and doc != summary else ""
    return summary, source_description(index, module, node, detail)


def assignments(nodes: list[ast.stmt]) -> dict[str, ast.expr]:
    """Return simple assignments in a class body."""
    result: dict[str, ast.expr] = {}
    for node in nodes:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                result[target.id] = node.value
    return result


def decorator_name(node: ast.expr) -> str:
    """Return the final name of a decorator or call."""
    match node:
        case ast.Call(func=func):
            return decorator_name(func)
        case ast.Attribute(attr=name) | ast.Name(id=name):
            return name
        case _:
            return ""


def slug(value: str) -> str:
    """Return a stable identifier."""
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
