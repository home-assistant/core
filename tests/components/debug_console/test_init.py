"""Tests for the Debug console integration setup."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.debug_console.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def development_version() -> Generator[None]:
    """Run as a development version, which enables the console once."""
    with patch("homeassistant.components.debug_console.IS_DEVELOPMENT_VERSION", True):
        yield


@pytest.mark.usefixtures("development_version")
async def test_enabled_once_on_development_version(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test development versions enable the console the first time."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_loaded_entries(DOMAIN)) == 1
    assert hass_storage[DOMAIN]["data"] == {"enabled_automatically": True}


@pytest.mark.usefixtures("development_version")
async def test_stays_disabled_on_development_version(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test the console is not enabled again, after the user removed it."""
    hass_storage[DOMAIN] = {
        "version": 1,
        "key": DOMAIN,
        "data": {"enabled_automatically": True},
    }

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)


async def test_not_enabled_on_release_version(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test release versions leave enabling the console to the user."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert DOMAIN not in hass_storage
