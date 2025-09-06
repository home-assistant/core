"""Tests for the Alexa Devices integration."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.const import (
    CONF_LOGIN_DATA,
    CONF_SITE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import TEST_PASSWORD, TEST_SERIAL_NUMBER, TEST_USERNAME

from tests.common import MockConfigEntry


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_SERIAL_NUMBER)}
    )
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("minor_version", "country", "site_data", "site_login_data"),
    [
        # Standard migration case
        (1, "US", None, None),
        # Edge case #1: no country, site already in login data
        (1, None, None, "https://www.amazon.com"),
        # Edge case #2: no country, site in data (wrong place), minor version 1
        (1, None, "https://www.amazon.com", None),
        # Edge case #3: no country, site in data (wrong place), minor version 2
        (2, None, "https://www.amazon.com", None),
    ],
)
async def test_migrate_entry(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    minor_version: int,
    country: str | None,
    site_data: str | None,
    site_login_data: str | None,
) -> None:
    """Test successful migration of entry data."""

    data = {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_LOGIN_DATA: {"session": "test-session"},
    }

    if country:
        data[CONF_COUNTRY] = country

    if site_data:
        data[CONF_SITE] = site_data

    if site_login_data:
        data[CONF_LOGIN_DATA].update({CONF_SITE: site_login_data})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Amazon Test Account",
        data=data,
        unique_id=TEST_USERNAME,
        version=1,
        minor_version=minor_version,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.minor_version == 3
    assert config_entry.data[CONF_LOGIN_DATA][CONF_SITE] == "https://www.amazon.com"
