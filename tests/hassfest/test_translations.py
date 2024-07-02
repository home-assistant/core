"""Tests for hassfest translations."""

import pytest
import voluptuous as vol

from script.hassfest import translations


def test_string_with_no_placeholders_in_single_quotes() -> None:
    """Test string with no placeholders in single quotes."""
    schema = vol.Schema(translations.string_no_single_quoted_placeholders)

    with pytest.raises(vol.Invalid):
        schema("This has '{placeholder}' in single quotes")

    for value in (
        'This has "{placeholder}" in double quotes',
        "Simple {placeholder}",
        "No placeholder",
    ):
        schema(value)
