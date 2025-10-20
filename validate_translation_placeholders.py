#!/usr/bin/env python3
"""Validate that translation placeholders match between code and strings.json."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any


class PlaceholderValidator:
    """Validate translation placeholders."""

    def __init__(self) -> None:
        """Initialize validator."""
        self.mismatches: list[dict[str, Any]] = []
        self.components_path = Path("homeassistant/components")

    def extract_placeholders_from_string(self, text: str) -> set[str]:
        """Extract placeholder names from a translation string."""
        # Match {placeholder_name} patterns
        return set(re.findall(r"\{(\w+)\}", text))

    def get_translation_strings(
        self, component: str, strings_file: Path
    ) -> dict[str, Any]:
        """Load strings.json for a component."""
        try:
            with open(strings_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def find_translation_string(
        self, strings_data: dict[str, Any], translation_key: str
    ) -> str | None:
        """Find translation string by key in nested structure."""
        # Check in exceptions
        if "exceptions" in strings_data:
            if translation_key in strings_data["exceptions"]:
                return strings_data["exceptions"][translation_key].get("message")

        # Check in issues
        if "issues" in strings_data:
            if translation_key in strings_data["issues"]:
                return strings_data["issues"][translation_key].get("description")

        # Check in services
        if "services" in strings_data:
            for service_name, service_data in strings_data["services"].items():
                if translation_key == service_name:
                    return service_data.get("description")

        # Check in config errors/aborts
        if "config" in strings_data:
            if "error" in strings_data["config"]:
                if translation_key in strings_data["config"]["error"]:
                    return strings_data["config"]["error"][translation_key]
            if "abort" in strings_data["config"]:
                if translation_key in strings_data["config"]["abort"]:
                    return strings_data["config"]["abort"][translation_key]

        # Check in entity state attributes
        if "entity" in strings_data:
            for platform, entities in strings_data["entity"].items():
                if isinstance(entities, dict):
                    for entity_key, entity_data in entities.items():
                        if isinstance(entity_data, dict):
                            if "state_attributes" in entity_data:
                                for attr_key, attr_data in entity_data[
                                    "state_attributes"
                                ].items():
                                    if translation_key == attr_key:
                                        if isinstance(attr_data, dict):
                                            return attr_data.get("name")

        return None

    def extract_dict_keys(self, node: ast.AST) -> set[str] | None:
        """Extract keys from a dictionary AST node."""
        if isinstance(node, ast.Dict):
            keys = set()
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
            return keys
        return None

    def process_file(self, file_path: Path) -> None:
        """Process a Python file for translation placeholder usage."""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError):
            return

        component = file_path.parent.name
        strings_file = file_path.parent / "strings.json"

        if not strings_file.exists():
            return

        strings_data = self.get_translation_strings(component, strings_file)

        for node in ast.walk(tree):
            # Look for function calls with translation_placeholders
            if isinstance(node, ast.Call):
                translation_key = None
                translation_domain = None
                placeholder_keys: set[str] | None = None

                # Extract keyword arguments
                for keyword in node.keywords:
                    if keyword.arg == "translation_key":
                        if isinstance(keyword.value, ast.Constant):
                            translation_key = keyword.value.value
                    elif keyword.arg == "translation_domain":
                        if isinstance(keyword.value, ast.Name):
                            # Assume DOMAIN constant
                            translation_domain = component
                    elif keyword.arg == "translation_placeholders":
                        placeholder_keys = self.extract_dict_keys(keyword.value)

                # Only check if we have both translation_key and translation_placeholders
                if translation_key and placeholder_keys is not None:
                    # Find the translation string
                    translation_string = self.find_translation_string(
                        strings_data, translation_key
                    )

                    if translation_string:
                        # Extract placeholders from the translation string
                        string_placeholders = self.extract_placeholders_from_string(
                            translation_string
                        )

                        # Check for mismatches
                        if placeholder_keys != string_placeholders:
                            missing_in_string = placeholder_keys - string_placeholders
                            extra_in_string = string_placeholders - placeholder_keys

                            if missing_in_string or extra_in_string:
                                self.mismatches.append(
                                    {
                                        "file": str(file_path),
                                        "component": component,
                                        "translation_key": translation_key,
                                        "code_placeholders": sorted(placeholder_keys),
                                        "string_placeholders": sorted(
                                            string_placeholders
                                        ),
                                        "missing_in_string": sorted(missing_in_string),
                                        "extra_in_string": sorted(extra_in_string),
                                        "translation_string": translation_string,
                                    }
                                )

    def validate_all(self) -> None:
        """Validate all components."""
        # Find all Python files with translation_placeholders
        for py_file in self.components_path.rglob("*.py"):
            if "translation_placeholders" in py_file.read_text():
                self.process_file(py_file)

    def print_report(self) -> None:
        """Print validation report."""
        if not self.mismatches:
            print("✅ No translation placeholder mismatches found!")
            return

        print(f"❌ Found {len(self.mismatches)} translation placeholder mismatches:\n")

        for idx, mismatch in enumerate(self.mismatches, 1):
            print(f"{idx}. {mismatch['file']}")
            print(f"   Component: {mismatch['component']}")
            print(f"   Translation key: {mismatch['translation_key']}")
            print(f"   Code passes: {mismatch['code_placeholders']}")
            print(f"   String expects: {mismatch['string_placeholders']}")

            if mismatch["missing_in_string"]:
                print(
                    f"   ⚠️  Missing in strings.json: {mismatch['missing_in_string']}"
                )
            if mismatch["extra_in_string"]:
                print(
                    f"   ⚠️  Unused in strings.json: {mismatch['extra_in_string']}"
                )

            print(f"   Translation string: {mismatch['translation_string'][:100]}...")
            print()


def main() -> None:
    """Run validation."""
    validator = PlaceholderValidator()
    print("Validating translation placeholders...")
    validator.validate_all()
    validator.print_report()


if __name__ == "__main__":
    main()
