"""Test the init file code."""

from unittest.mock import patch

import pytest
from zeversolar import ZeverSolarData
from zeversolar.exceptions import ZeverSolarTimeout

import homeassistant.components.zeversolar.__init__ as init
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


async def test_async_setup_entry_fails(
    hass: HomeAssistant, config_entry: MockConfigEntry, zeversolar_data: ZeverSolarData
) -> None:
    """Test to start the integration when inverter is offline (e.g. at night). Must raise a ConfigEntryNotReady error."""

    config_entry.add_to_hass(hass)

    with (
        patch("zeversolar.ZeverSolarClient.get_data", side_effect=ZeverSolarTimeout),
        pytest.raises(ConfigEntryNotReady),
    ):
        await init.async_setup_entry(hass, config_entry)


    with (
        patch("homeassistant.components.zeversolar.PLATFORMS", []),
        patch("zeversolar.ZeverSolarClient.get_data", return_value=zeversolar_data),
    ):
        config_entry.add_to_hass(hass)

        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED


async def test_load_entry_fails(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test to start the integration when inverter is offline (e.g. at night)."""

    with (
        patch("homeassistant.components.zeversolar.PLATFORMS", [Platform.SENSOR]),
        patch("zeversolar.ZeverSolarClient.get_data", side_effect=ZeverSolarTimeout),
    ):
        config_entry.add_to_hass(hass)

        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is False
        assert config_entry.state is ConfigEntryState.SETUP_RETRY
