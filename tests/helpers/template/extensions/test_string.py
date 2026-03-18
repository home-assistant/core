"""Test string template extension."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template


def test_ordinal(hass: HomeAssistant) -> None:
    """Test the ordinal filter."""
    tests = [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (5, "5th"),
        (12, "12th"),
        (100, "100th"),
        (101, "101st"),
    ]

    for value, expected in tests:
        assert (
            template.Template(f"{{{{ {value} | ordinal }}}}", hass).async_render()
            == expected
        )


def test_slugify(hass: HomeAssistant) -> None:
    """Test the slugify filter."""
    # Test as global function
    assert (
        template.Template('{{ slugify("Home Assistant") }}', hass).async_render()
        == "home_assistant"
    )

    # Test as filter
    assert (
        template.Template('{{ "Home Assistant" | slugify }}', hass).async_render()
        == "home_assistant"
    )

    # Test with custom separator as global
    assert (
        template.Template('{{ slugify("Home Assistant", "-") }}', hass).async_render()
        == "home-assistant"
    )

    # Test with custom separator as filter
    assert (
        template.Template('{{ "Home Assistant" | slugify("-") }}', hass).async_render()
        == "home-assistant"
    )


def test_urlencode(hass: HomeAssistant) -> None:
    """Test the urlencode method."""
    # Test with dictionary
    tpl = template.Template(
        "{% set dict = {'foo': 'x&y', 'bar': 42} %}{{ dict | urlencode }}",
        hass,
    )
    assert tpl.async_render() == "foo=x%26y&bar=42"

    # Test with string
    tpl = template.Template(
        "{% set string = 'the quick brown fox = true' %}{{ string | urlencode }}",
        hass,
    )
    assert tpl.async_render() == "the%20quick%20brown%20fox%20%3D%20true"


def test_string_functions_with_non_string_input(hass: HomeAssistant) -> None:
    """Test string functions with non-string input (automatic conversion)."""
    # Test ordinal with integer
    assert template.Template("{{ 42 | ordinal }}", hass).async_render() == "42nd"

    # Test slugify with integer - Note: Jinja2 may return integer for simple cases
    result = template.Template("{{ 123 | slugify }}", hass).async_render()
    # Accept either string or integer result for simple numeric cases
    assert result in ["123", 123]


def test_ordinal_edge_cases(hass: HomeAssistant) -> None:
    """Test ordinal function with edge cases."""
    # Test teens (11th, 12th, 13th should all be 'th')
    teens_tests = [
        (11, "11th"),
        (12, "12th"),
        (13, "13th"),
        (111, "111th"),
        (112, "112th"),
        (113, "113th"),
    ]

    for value, expected in teens_tests:
        assert (
            template.Template(f"{{{{ {value} | ordinal }}}}", hass).async_render()
            == expected
        )

    # Test other numbers ending in 1, 2, 3
    other_tests = [
        (21, "21st"),
        (22, "22nd"),
        (23, "23rd"),
        (121, "121st"),
        (122, "122nd"),
        (123, "123rd"),
    ]

    for value, expected in other_tests:
        assert (
            template.Template(f"{{{{ {value} | ordinal }}}}", hass).async_render()
            == expected
        )


def test_slugify_various_separators(hass: HomeAssistant) -> None:
    """Test slugify with various separators."""
    test_cases = [
        ("Hello World", "_", "hello_world"),
        ("Hello World", "-", "hello-world"),
        ("Hello World", ".", "hello.world"),
        ("Hello-World_Test", "~", "hello~world~test"),
    ]

    for text, separator, expected in test_cases:
        # Test as global function
        assert (
            template.Template(
                f'{{{{ slugify("{text}", "{separator}") }}}}', hass
            ).async_render()
            == expected
        )

        # Test as filter
        assert (
            template.Template(
                f'{{{{ "{text}" | slugify("{separator}") }}}}', hass
            ).async_render()
            == expected
        )


def test_urlencode_various_types(hass: HomeAssistant) -> None:
    """Test urlencode with various data types."""
    # Test with nested dictionary values
    tpl = template.Template(
        "{% set data = {'key': 'value with spaces', 'num': 123} %}{{ data | urlencode }}",
        hass,
    )
    result = tpl.async_render()
    # URL encoding can have different order, so check both parts are present
    # Note: urllib.parse.urlencode uses + for spaces in form data
    assert "key=value+with+spaces" in result
    assert "num=123" in result

    # Test with special characters
    tpl = template.Template(
        "{% set data = {'special': 'a+b=c&d'} %}{{ data | urlencode }}",
        hass,
    )
    assert tpl.async_render() == "special=a%2Bb%3Dc%26d"
