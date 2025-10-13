"""Test regex template extension."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template


def test_regex_match(hass: HomeAssistant) -> None:
    """Test regex_match method."""

    result = render(
        hass, r"""{{ '123-456-7890' | regex_match('(\\d{3})-(\\d{3})-(\\d{4})') }}"""
    )
    assert result is True

    result = render(hass, """{{ 'Home Assistant test' | regex_match('home', True) }}""")
    assert result is True

    result = render(
        hass, """    {{ 'Another Home Assistant test' | regex_match('Home') }}"""
    )
    assert result is False

    result = render(hass, """{{ ['Home Assistant test'] | regex_match('.*Assist') }}""")
    assert result is True


def test_match_test(hass: HomeAssistant) -> None:
    """Test match test."""

    result = render(
        hass, r"""{{ '123-456-7890' is match('(\\d{3})-(\\d{3})-(\\d{4})') }}"""
    )
    assert result is True


def test_regex_search(hass: HomeAssistant) -> None:
    """Test regex_search method."""

    result = render(
        hass, r"""{{ '123-456-7890' | regex_search('(\\d{3})-(\\d{3})-(\\d{4})') }}"""
    )
    assert result is True

    result = render(
        hass, """{{ 'Home Assistant test' | regex_search('home', True) }}"""
    )
    assert result is True

    result = render(
        hass, """    {{ 'Another Home Assistant test' | regex_search('Home') }}"""
    )
    assert result is True

    result = render(hass, """{{ ['Home Assistant test'] | regex_search('Assist') }}""")
    assert result is True


def test_search_test(hass: HomeAssistant) -> None:
    """Test search test."""

    result = render(
        hass, r"""{{ '123-456-7890' is search('(\\d{3})-(\\d{3})-(\\d{4})') }}"""
    )
    assert result is True


def test_regex_replace(hass: HomeAssistant) -> None:
    """Test regex_replace method."""

    result = render(hass, r"""{{ 'Hello World' | regex_replace('(Hello\\s)',) }}""")
    assert result == "World"

    result = render(
        hass, """{{ ['Home hinderant test'] | regex_replace('hinder', 'Assist') }}"""
    )
    assert result == ["Home Assistant test"]


def test_regex_findall(hass: HomeAssistant) -> None:
    """Test regex_findall method."""

    result = render(
        hass, """{{ 'Flight from JFK to LHR' | regex_findall('([A-Z]{3})') }}"""
    )
    assert result == ["JFK", "LHR"]


def test_regex_findall_index(hass: HomeAssistant) -> None:
    """Test regex_findall_index method."""

    result = render(
        hass,
        """{{ 'Flight from JFK to LHR' | regex_findall_index('([A-Z]{3})', 0) }}""",
    )
    assert result == "JFK"

    result = render(
        hass,
        """{{ 'Flight from JFK to LHR' | regex_findall_index('([A-Z]{3})', 1) }}""",
    )
    assert result == "LHR"


def test_regex_ignorecase_parameter(hass: HomeAssistant) -> None:
    """Test ignorecase parameter across all regex functions."""
    # Test regex_match with ignorecase

    result = render(hass, """{{ 'TEST' | regex_match('test', True) }}""")
    assert result is True

    # Test regex_search with ignorecase

    result = render(hass, """{{ 'TEST STRING' | regex_search('test', True) }}""")
    assert result is True

    # Test regex_replace with ignorecase

    result = render(hass, """{{ 'TEST' | regex_replace('test', 'replaced', True) }}""")
    assert result == "replaced"

    # Test regex_findall with ignorecase

    result = render(hass, """{{ 'TEST test Test' | regex_findall('test', True) }}""")
    assert result == ["TEST", "test", "Test"]


def test_regex_with_non_string_input(hass: HomeAssistant) -> None:
    """Test regex functions with non-string input (automatic conversion)."""
    # Test with integer

    result = render(hass, r"""{{ 12345 | regex_match('\\d+') }}""")
    assert result is True

    # Test with list (string conversion)

    result = render(hass, r"""{{ [1, 2, 3] | regex_search('\\d') }}""")
    assert result is True


def test_regex_edge_cases(hass: HomeAssistant) -> None:
    """Test regex functions with edge cases."""
    # Test with empty string

    result = render(hass, """{{ '' | regex_match('.*') }}""")
    assert result is True

    # Test regex_findall_index with out of bounds index
    tpl = template.Template(
        """{{ 'test' | regex_findall_index('t', 5) }}""",
        hass,
    )
    with pytest.raises(TemplateError):
        tpl.async_render()

    # Test with invalid regex pattern
    tpl = template.Template(
        """{{ 'test' | regex_match('[') }}""",
        hass,
    )
    with pytest.raises(TemplateError):  # re.error wrapped in TemplateError
        tpl.async_render()


def test_regex_groups_and_replacement_patterns(hass: HomeAssistant) -> None:
    """Test regex with groups and replacement patterns."""
    # Test replacement with groups

    result = render(
        hass, r"""{{ 'John Doe' | regex_replace('(\\w+) (\\w+)', '\\2, \\1') }}"""
    )
    assert result == "Doe, John"

    # Test findall with groups
    tpl = template.Template(
        r"""{{ 'Email: test@example.com, Phone: 123-456-7890' | regex_findall('(\\w+@\\w+\\.\\w+)|(\\d{3}-\\d{3}-\\d{4})') }}""",
        hass,
    )
    result = tpl.async_render()
    # The result will contain tuples with empty strings for non-matching groups
    assert len(result) == 2
