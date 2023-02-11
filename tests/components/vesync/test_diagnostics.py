"""Tests for the diagnostics data provided by the VeSync integration."""
import json
from unittest.mock import patch

from aiohttp import ClientSession
from pyvesync.helpers import Helpers

from homeassistant.components.vesync import async_setup_entry
from homeassistant.components.vesync.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .common import (
    call_api_side_effect__no_devices,
    call_api_side_effect__single_device,
)

from tests.common import load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_get_diagnostics_for_config_entry__no_devices(
    hass: HomeAssistant,
    hass_client: ClientSession,
    config_entry: ConfigEntry,
    config: ConfigType,
):
    """Test diagnostics for config entry."""
    with patch.object(Helpers, "call_api") as call_api:
        call_api.side_effect = call_api_side_effect__no_devices
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        assert await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert isinstance(diag, dict)
    assert diag == json.loads(
        load_fixture(
            "vesync_get_diagnostics_for_config_entry__no_devices.json", "vesync"
        )
    )


async def test_get_diagnostics_for_config_entry__single_device(
    hass: HomeAssistant,
    hass_client: ClientSession,
    config_entry: ConfigEntry,
    config: ConfigType,
):
    """Test diagnostics for config entry."""
    with patch.object(Helpers, "call_api") as call_api:
        call_api.side_effect = call_api_side_effect__single_device
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        assert await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert isinstance(diag, dict)
    assert diag == json.loads(
        load_fixture(
            "vesync_get_diagnostics_for_config_entry__single_device.json", "vesync"
        )
    )
