"""Validate translation placeholder consistency."""

from __future__ import annotations

import json
from pathlib import Path

from .const import INTEGRATIONS_DIR
from .develop import InvalidSubstitutionKey, substitute_reference
from .upload import generate_upload_data
from .util import extract_placeholders, flatten_translations


def validate_integration_placeholders(
    integration_name: str,
    integration_path: Path,
    flattened_english: dict[str, str],
) -> list[str]:
    """Validate placeholder consistency for an integration.

    Returns list of error messages.
    """
    errors = []

    for translation_file in (integration_path / "translations").glob("*.json"):
        locale = translation_file.stem

        # Skip things like `sensor.nl.json` and backup files
        if "." in locale:
            continue

        localized_data = json.loads(translation_file.read_text())
        localized_flat = flatten_translations(localized_data)

        for key, localized_value in localized_flat.items():
            full_key = f"component::{integration_name}::{key}"

            # Skip if key doesn't exist in English
            if full_key not in flattened_english:
                continue

            # Resolve references
            try:
                english_value = substitute_reference(
                    flattened_english[full_key], flattened_english
                )
                localized_value = substitute_reference(localized_value, localized_flat)
            except InvalidSubstitutionKey as err:
                errors.append(f"  [{locale}] {key}: {err}")
                continue

            # Extract placeholders from both versions
            try:
                english_placeholders = extract_placeholders(english_value)
            except ValueError as err:
                errors.append(
                    f"  [{locale}] Invalid format string in strings.json at {key}: {err}"
                )
                continue

            try:
                localized_placeholders = extract_placeholders(localized_value)
            except ValueError as err:
                errors.append(f"  [{locale}] Invalid format string at {key}: {err}")
                continue

            # Compare placeholders
            if english_placeholders != localized_placeholders:
                if english_placeholders < localized_placeholders:
                    errors.append(
                        f"  [{locale}] {key}: placeholders were added "
                        f"({localized_placeholders} > {english_placeholders})"
                    )
                else:
                    errors.append(
                        f"  [{locale}] {key}: placeholder mismatch "
                        f"({localized_placeholders} != {english_placeholders})"
                    )

    return errors


def run():
    """Run the validation."""

    # Load all English translations once
    translations = generate_upload_data()
    flattened_english = flatten_translations(translations)

    return_code = 0

    for integration_path in INTEGRATIONS_DIR.iterdir():
        if not (integration_path / "strings.json").is_file():
            continue

        integration = integration_path.name
        errors = validate_integration_placeholders(
            integration, integration_path, flattened_english
        )

        if errors:
            return_code = 1
            print(f"\n{integration}:")

            for error in errors:
                print(error)

    return return_code
