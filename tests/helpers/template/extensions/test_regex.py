"""Test regex template extension."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template


def test_regex_match(hass: HomeAssistant) -> None:
    """Test regex_match method."""
    tpl = template.Template(
        r"""
{{ '123-456-7890' | regex_match('(\\d{3})-(\\d{3})-(\\d{4})') }}
            """,
        hass,
    )
    assert tpl.async_render() is True

    tpl = template.Template(
        """
{{ 'Home Assistant test' | regex_match('home', True) }}
            """,
        hass,
    )
    assert tpl.async_render() is True

    tpl = template.Template(
        """
    {{ 'Another Home Assistant test' | regex_match('Home') }}
                    """,
        hass,
    )
    assert tpl.async_render() is False

    tpl = template.Template(
        """
{{ ['Home Assistant test'] | regex_match('.*Assist') }}
            """,
        hass,
    )
    assert tpl.async_render() is True


def test_match_test(hass: HomeAssistant) -> None:
    """Test match test."""
    tpl = template.Template(
        r"""
{{ '123-456-7890' is match('(\\d{3})-(\\d{3})-(\\d{4})') }}
            """,
        hass,
    )
    assert tpl.async_render() is True


def test_regex_search(hass: HomeAssistant) -> None:
    """Test regex_search method."""
    tpl = template.Template(
        r"""
{{ '123-456-7890' | regex_search('(\\d{3})-(\\d{3})-(\\d{4})') }}
            """,
        hass,
    )
    assert tpl.async_render() is True

    tpl = template.Template(
        """
{{ 'Home Assistant test' | regex_search('home', True) }}
            """,
        hass,
    )
    assert tpl.async_render() is True

    tpl = template.Template(
        """
    {{ 'Another Home Assistant test' | regex_search('Home') }}
                    """,
        hass,
    )
    assert tpl.async_render() is True

    tpl = template.Template(
        """
{{ ['Home Assistant test'] | regex_search('Assist') }}
            """,
        hass,
    )
    assert tpl.async_render() is True


def test_search_test(hass: HomeAssistant) -> None:
    """Test search test."""
    tpl = template.Template(
        r"""
{{ '123-456-7890' is search('(\\d{3})-(\\d{3})-(\\d{4})') }}
            """,
        hass,
    )
    assert tpl.async_render() is True


def test_regex_replace(hass: HomeAssistant) -> None:
    """Test regex_replace method."""
    tpl = template.Template(
        r"""
{{ 'Hello World' | regex_replace('(Hello\\s)',) }}
            """,
        hass,
    )
    assert tpl.async_render() == "World"

    tpl = template.Template(
        """
{{ ['Home hinderant test'] | regex_replace('hinder', 'Assist') }}
            """,
        hass,
    )
    assert tpl.async_render() == ["Home Assistant test"]


def test_regex_findall(hass: HomeAssistant) -> None:
    """Test regex_findall method."""
    tpl = template.Template(
        """
{{ 'Flight from JFK to LHR' | regex_findall('([A-Z]{3})') }}
            """,
        hass,
    )
    assert tpl.async_render() == ["JFK", "LHR"]


def test_regex_findall_index(hass: HomeAssistant) -> None:
    """Test regex_findall_index method."""
    tpl = template.Template(
        """
{{ 'Flight from JFK to LHR' | regex_findall_index('([A-Z]{3})', 0) }}
            """,
        hass,
    )
    assert tpl.async_render() == "JFK"

    tpl = template.Template(
        """
{{ 'Flight from JFK to LHR' | regex_findall_index('([A-Z]{3})', 1) }}
            """,
        hass,
    )
    assert tpl.async_render() == "LHR"


def test_regex_ignorecase_parameter(hass: HomeAssistant) -> None:
    """Test ignorecase parameter across all regex functions."""
    # Test regex_match with ignorecase
    tpl = template.Template(
        """
{{ 'TEST' | regex_match('test', True) }}
            """,
        hass,
    )
    assert tpl.async_render() is True

    # Test regex_search with ignorecase
    tpl = template.Template(
        """
{{ 'TEST STRING' | regex_search('test', True) }}
            """,
        hass,
    )
    assert tpl.async_render() is True

    # Test regex_replace with ignorecase
    tpl = template.Template(
        """
{{ 'TEST' | regex_replace('test', 'replaced', True) }}
            """,
        hass,
    )
    assert tpl.async_render() == "replaced"

    # Test regex_findall with ignorecase
    tpl = template.Template(
        """
{{ 'TEST test Test' | regex_findall('test', True) }}
            """,
        hass,
    )
    assert tpl.async_render() == ["TEST", "test", "Test"]


def test_regex_with_non_string_input(hass: HomeAssistant) -> None:
    """Test regex functions with non-string input (automatic conversion)."""
    # Test with integer
    tpl = template.Template(
        r"""
{{ 12345 | regex_match('\\d+') }}
            """,
        hass,
    )
    assert tpl.async_render() is True

    # Test with list (string conversion)
    tpl = template.Template(
        r"""
{{ [1, 2, 3] | regex_search('\\d') }}
            """,
        hass,
    )
    assert tpl.async_render() is True


def test_regex_edge_cases(hass: HomeAssistant) -> None:
    """Test regex functions with edge cases."""
    # Test with empty string
    tpl = template.Template(
        """
{{ '' | regex_match('.*') }}
            """,
        hass,
    )
    assert tpl.async_render() is True

    # Test regex_findall_index with out of bounds index
    tpl = template.Template(
        """
{{ 'test' | regex_findall_index('t', 5) }}
            """,
        hass,
    )
    with pytest.raises(TemplateError):
        tpl.async_render()

    # Test with invalid regex pattern
    tpl = template.Template(
        """
{{ 'test' | regex_match('[') }}
            """,
        hass,
    )
    with pytest.raises(TemplateError):  # re.error wrapped in TemplateError
        tpl.async_render()


def test_regex_groups_and_replacement_patterns(hass: HomeAssistant) -> None:
    """Test regex with groups and replacement patterns."""
    # Test replacement with groups
    tpl = template.Template(
        r"""
{{ 'John Doe' | regex_replace('(\\w+) (\\w+)', '\\2, \\1') }}
            """,
        hass,
    )
    assert tpl.async_render() == "Doe, John"

    # Test findall with groups
    tpl = template.Template(
        r"""
{{ 'Email: test@example.com, Phone: 123-456-7890' | regex_findall('(\\w+@\\w+\\.\\w+)|(\\d{3}-\\d{3}-\\d{4})') }}
            """,
        hass,
    )
    result = tpl.async_render()
    # The result will contain tuples with empty strings for non-matching groups
    assert len(result) == 2
