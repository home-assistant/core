"""Test the Map initialization."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.map import DOMAIN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockModule, mock_integration


@pytest.fixture
def mock_onboarding_not_done() -> Generator[MagicMock, None, None]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=False,
    ) as mock_onboarding:
        yield mock_onboarding


@pytest.fixture
def mock_onboarding_done() -> Generator[MagicMock, None, None]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=True,
    ) as mock_onboarding:
        yield mock_onboarding


@pytest.fixture
def mock_create_map_dashboard() -> Generator[MagicMock, None, None]:
    """Mock the create map dashboard function."""
    with patch(
        "homeassistant.components.map._create_map_dashboard",
    ) as mock_create_map_dashboard:
        yield mock_create_map_dashboard


async def test_create_dashboards_when_onboarded(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_onboarding_done,
    mock_create_map_dashboard,
) -> None:
    """Test we create map dashboard when onboarded."""
    # Mock the lovelace integration to prevent it from creating a map dashboard
    mock_integration(hass, MockModule("lovelace"))

    assert await async_setup_component(hass, DOMAIN, {})

    mock_create_map_dashboard.assert_called_once()
    assert hass_storage[DOMAIN]["data"] == {"migrated": True}


async def test_create_dashboards_once_when_onboarded(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_onboarding_done,
    mock_create_map_dashboard,
) -> None:
    """Test we create map dashboard once when onboarded."""
    hass_storage[DOMAIN] = {
        "version": 1,
        "minor_version": 1,
        "key": "map",
        "data": {"migrated": True},
    }

    # Mock the lovelace integration to prevent it from creating a map dashboard
    mock_integration(hass, MockModule("lovelace"))

    assert await async_setup_component(hass, DOMAIN, {})

    mock_create_map_dashboard.assert_not_called()
    assert hass_storage[DOMAIN]["data"] == {"migrated": True}


async def test_create_dashboards_when_not_onboarded(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_onboarding_not_done,
    mock_create_map_dashboard,
) -> None:
    """Test we do not create map dashboard when not onboarded."""
    # Mock the lovelace integration to prevent it from creating a map dashboard
    mock_integration(hass, MockModule("lovelace"))

    assert await async_setup_component(hass, DOMAIN, {})

    mock_create_map_dashboard.assert_not_called()
    assert hass_storage[DOMAIN]["data"] == {"migrated": True}


async def test_create_issue_when_not_manually_configured(hass: HomeAssistant) -> None:
    """Test creating issue registry issues."""
    assert await async_setup_component(hass, DOMAIN, {})

    issue_registry = ir.async_get(hass)
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_map"
    )


async def test_create_issue_when_manually_configured(hass: HomeAssistant) -> None:
    """Test creating issue registry issues."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, "deprecated_yaml_map")
