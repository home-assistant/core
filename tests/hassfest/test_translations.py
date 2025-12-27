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


@pytest.mark.parametrize(
    "translation_string",
    [
        "An example is: https://example.com.",
        "www.example.com",
    ],
)
def test_no_placeholders_used_for_urls(translation_string: str) -> None:
    """Test string with no placeholders in single quotes."""
    schema = vol.Schema(translations.translation_value_validator)

    with pytest.raises(vol.Invalid):
        schema(translation_string)
