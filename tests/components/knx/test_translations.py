"""Test KNX Schema Translations."""

from enum import Enum
import json
import logging
from pathlib import Path
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components.knx.const import CONF_LABEL
from homeassistant.components.knx.schema import SerializableSchema, VolMarkerDesc
from homeassistant.components.knx.sensor import UiSensorConfig
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

_LOGGER = logging.getLogger(__name__)


class TestSchemaTranslations:
    """Tests ensuring the completeness and correctness of Schema-related translation keys."""

    def test_required_schema_translations_exist(
        self, hass: HomeAssistant, knx: KNXTestKit
    ) -> None:
        """Validate that all required translation paths from config schemas are present in en.json.

        Steps:
        1) Collect all required translation keys
           from registered schemas.
        2) Load en.json and verify that each required key exists.
        3) For missing keys, insert "PLACEHOLDER" and log the updated JSON structure
           as a template for easy copy & paste.
        4) Fail the test if any required translations are missing.
        """

        # 1) Collect all required translation keys
        required_translation_keys = self._get_required_schema_translation_keys()

        # 2) Load the existing translations from en.json
        translations = self._load_translations()

        # 3) Find missing translations
        missing_keys = [
            path
            for path in required_translation_keys
            if not self._nested_dict_path_exists(translations, path)
        ]

        if missing_keys:
            # Insert placeholder entries for missing translation paths
            for path in missing_keys:
                self._create_path_and_set_placeholder(path, translations)

            # Log a helpful message containing the updated JSON structure
            _LOGGER.info(
                "\n\n+--------------------------------------------------------------+\n"
                "| Missing Schema Translations in 'strings.json'                |\n"
                "|                                                              |\n"
                "| A template with placeholder values is provided below.        |\n"
                "| Copy and paste it into the 'strings.json' file, replacing    |\n"
                "| the 'config_panel' node. Make sure to replace the            |\n"
                "| placeholders with the correct translations.                  |\n"
                "+--------------------------------------------------------------+\n"
                ' "config_panel": %s\n'
                "+--------------------------------------------------------------+\n",
                json.dumps(
                    translations.get("config_panel", {}),
                    indent=2,
                    ensure_ascii=False,
                ),
            )

            # Log all missing translation paths
            _LOGGER.error(
                "\nMissing translations:\n - %s\n", "\n - ".join(missing_keys)
            )
            pytest.fail("Missing translations in en.json")

        assert True  # If no missing translations, the test passes

    def test_no_unused_schema_translations(
        self, hass: HomeAssistant, knx: KNXTestKit
    ) -> None:
        """Check that there are no unused (dead) translation paths in en.json.

        Steps:
        1) Collect all required translation keys from the config schemas.
        2) Flatten the 'config_panel' node in en.json into dotted paths.
        3) Compare the flattened translation keys with the required keys.
        4) Fail the test if any translation paths are found that are not required.
        """

        # 1) Collect all required translation keys
        required_translation_keys = self._get_required_schema_translation_keys()

        # 2) Load the existing translations from en.json
        translations = self._load_translations()

        # 3) Flatten the `config_panel` node into dotted paths
        flattened_keys = self._flatten_nested_dict_keys(
            translations.get("config_panel", {}), parent_key="config_panel"
        )

        # 4) Identify any paths that are not required
        unused_keys = [
            key for key in flattened_keys if key not in required_translation_keys
        ]
        if unused_keys:
            _LOGGER.warning(
                "\nUnused translations:\n - %s\n", "\n - ".join(unused_keys)
            )
            pytest.fail("Unused schema translations in en.json")

        assert True  # If no unused translations, the test passes

    def test_no_placeholder_values_in_translations(
        self, hass: HomeAssistant, knx: KNXTestKit
    ) -> None:
        """Check that there are no "PLACEHOLDER" values in the translation file.

        Steps:
        1) Load the existing translations from en.json.
        2) Traverse all nested keys in the dictionary.
        3) Fail the test if any key is assigned the value "PLACEHOLDER".
        """

        # 1) Load the existing translations from en.json
        translations = self._load_translations()

        # 2) Collect all paths whose Value == "PLACEHOLDER"
        placeholder_paths = self._collect_placeholder_paths(translations)

        # 3) If there are any placeholder paths, fail the test and log them
        if placeholder_paths:
            _LOGGER.error(
                "Found 'PLACEHOLDER' values in the following paths:\n - %s",
                "\n - ".join(placeholder_paths),
            )
            pytest.fail("Translations contain placeholder values.")

        assert True  # No placeholder values found => test passes

    def _collect_placeholder_paths(
        self, data: dict[str, Any], parent_key: str = ""
    ) -> list[str]:
        """Recursively collect all dotted paths in 'data' whose value is "PLACEHOLDER".

        Args:
            data (dict[str, Any]): The (possibly nested) translations dictionary.
            parent_key (str): Current path context used for recursion.

        Returns:
            list[str]: A list of dotted paths where the value is "PLACEHOLDER".

        """
        placeholder_paths = []

        for key, value in data.items():
            # Build a dotted path
            full_path = f"{parent_key}.{key}" if parent_key else key

            if isinstance(value, dict):
                # Recurse into nested dictionaries
                placeholder_paths.extend(
                    self._collect_placeholder_paths(value, full_path)
                )
            elif value == "PLACEHOLDER":
                placeholder_paths.append(full_path)

        return placeholder_paths

    @staticmethod
    def _load_translations() -> dict[str, Any]:
        """Load the strings.json translation file and return its content as a dictionary.

        Returns:
            dict[str, Any]: Parsed JSON content of the translation file.

        """
        translations_path = Path("homeassistant/components/knx/strings.json")
        with translations_path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)

    def _get_required_schema_translation_keys(self) -> list[str]:
        """Gather all translation keys required by the KNX schemas in dotted notation.

        Returns:
            list[str]: A sorted list of required translation keys.

        """
        # Here, you can add other config classes as needed
        config_classes = [UiSensorConfig]

        all_required_keys: list[str] = []
        for config_cls in config_classes:
            # Collect the translation keys from each config class
            platform = config_cls.get_platform()
            schema_obj = config_cls.get_schema()
            all_required_keys.extend(
                self._collect_translation_keys_from_schema(platform, schema_obj)
            )

        return all_required_keys

    def _collect_translation_keys_from_schema(
        self, platform: str, schema_input: Any, current_path: str | None = None
    ) -> list[str]:
        """Recursively collect translation keys from a given schema.

        Args:
            platform (str): The platform identifier (e.g., "sensor") to prefix translation keys.
            schema_input (Any): The schema object, which may be translatable or serializable.
            current_path (Optional[str]): Current dotted path context during recursion.

        Returns:
            List[str]: A sorted list of discovered translation paths.

        """
        discovered_paths: set[str] = set()

        # Define buckets for config and options
        config_bucket: str = f"config_panel.config.{platform}"
        options_bucket: str = "config_panel.options"

        # Handle different types of schema_input
        if isinstance(schema_input, (vol.Any, vol.All)):
            for validator in schema_input.validators:
                discovered_paths.update(
                    self._collect_translation_keys_from_schema(
                        platform, validator, current_path
                    )
                )
            return discovered_paths

        if isinstance(schema_input, vol.Coerce):
            schema_dict = schema_input.type
            if issubclass(schema_dict, Enum):
                discovered_paths.update(
                    f"{options_bucket}.{schema_dict.__name__.lower()}.{key}.{CONF_LABEL}"
                    for key in schema_dict
                )

        if isinstance(schema_input, vol.In):
            node_name = current_path.split(".")[-1] if current_path else None
            if node_name:
                discovered_paths.update(
                    f"{options_bucket}.{node_name.lower()}.{key.replace('.', '')}.{CONF_LABEL}"
                    for key in schema_input.container
                )
            schema_dict = schema_input.container

        if isinstance(schema_input, SerializableSchema):
            schema_dict = schema_input.get_schema()
            if isinstance(schema_dict, vol.Schema):
                schema_dict = schema_dict.schema
        else:
            schema_dict = schema_input

        # Recursively traverses nested dictionary structures.
        # Note: This code needs refactoring, but it will be updated anyway
        # to address the config_panel limitation.
        if isinstance(schema_dict, dict):
            for key, value in schema_dict.items():
                if isinstance(key, vol.Marker) and not isinstance(key, vol.Remove):
                    if key.description and isinstance(key.description, VolMarkerDesc):
                        desc = key.description
                        for tkey in desc.translation_keys:
                            full_path = (
                                f"{config_bucket}.{current_path}.{key}.{tkey}"
                                if current_path
                                else f"{config_bucket}.{key}.{tkey}"
                            )
                            discovered_paths.add(full_path)

                nested_path = f"{current_path}.{key}" if current_path else key
                discovered_paths.update(
                    self._collect_translation_keys_from_schema(
                        platform, value, nested_path
                    )
                )

        def custom_sort(key: str) -> str:
            """Sort by bucket and path depth."""
            for bucket in (config_bucket, options_bucket):
                if key.startswith(bucket):
                    depth = len(key.split("."))
                    return f"{bucket}.{depth:03d}{key[len(bucket) :]}"
            return key

        return sorted(discovered_paths, key=custom_sort)

    @staticmethod
    def _nested_dict_path_exists(data: dict[str, Any], dotted_path: str) -> bool:
        """Check if a dotted path exists in a nested dictionary.

        Example:
            data = {"a": {"b": {"c": 123}}}
            dotted_path = "a.b.c" -> True

        Args:
            data (dict[str, Any]): The dictionary to inspect.
            dotted_path (str): The dotted path (e.g., "key1.key2.key3").

        Returns:
            bool: True if the path exists, False otherwise.

        """
        try:
            current = data
            for part in dotted_path.split("."):
                current = current[part]
        except (KeyError, TypeError):
            return False
        else:
            return True

    @staticmethod
    def _create_path_and_set_placeholder(
        dotted_path: str, target_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """Ensure a nested dotted path exists in the dictionary and set the final key to "PLACEHOLDER".

        Args:
            dotted_path (str): Path in the form "key1.key2.key3".
            target_dict (dict[str, Any]): Dictionary to be updated.

        Returns:
            dict[str, Any]: Updated dictionary with the new path set to "PLACEHOLDER".

        """
        current = target_dict
        *keys, last_key = dotted_path.split(".")

        # Create intermediate dicts if they don't exist
        for key in keys:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[last_key] = "PLACEHOLDER"
        return target_dict

    @classmethod
    def _flatten_nested_dict_keys(
        cls, data: dict[str, Any], parent_key: str = ""
    ) -> list[str]:
        """Flatten a nested dictionary into a list of dotted paths.

        Example:
            data = {"a": {"b": {"c": 123}}}
            parent_key = "root"
            result -> ["root.a.b.c"]

        Args:
            data (dict[str, Any]): The nested dictionary.
            parent_key (str): Root key to prepend to the dotted path.

        Returns:
            list[str]: List of flattened dotted paths.

        """
        paths = []

        for key, value in data.items():
            # Construct the current dotted path
            full_key = f"{parent_key}.{key}" if parent_key else key
            if isinstance(value, dict):
                # Recurse into nested dictionaries
                paths.extend(cls._flatten_nested_dict_keys(value, full_key))
            else:
                # Leaf nodes are complete paths
                paths.append(full_key)

        return paths
