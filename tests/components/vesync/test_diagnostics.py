"""Tests for the diagnostics data provided by the VeSync integration."""
import json
from unittest.mock import patch

from aiohttp import ClientSession
from pyvesync.helpers import Helpers

from homeassistant.components.vesync import async_setup_entry
from homeassistant.components.vesync.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .common import (
    call_api_side_effect__no_devices,
    call_api_side_effect__single_fan,
    call_api_side_effect__single_humidifier,
)

from tests.common import load_fixture
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)


async def test_async_get_config_entry_diagnostics__no_devices(
    hass: HomeAssistant,
    hass_client: ClientSession,
    config_entry: ConfigEntry,
    config: ConfigType,
) -> None:
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
            "vesync_async_get_config_entry_diagnostics__no_devices.json", "vesync"
        )
    )


async def test_async_get_config_entry_diagnostics__single_humidifier(
    hass: HomeAssistant,
    hass_client: ClientSession,
    config_entry: ConfigEntry,
    config: ConfigType,
) -> None:
    """Test diagnostics for config entry."""
    with patch.object(Helpers, "call_api") as call_api:
        call_api.side_effect = call_api_side_effect__single_humidifier
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        assert await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert isinstance(diag, dict)
    assert diag == json.loads(
        load_fixture(
            "vesync_async_get_config_entry_diagnostics__single_humidifier.json",
            "vesync",
        )
    )


async def test_async_get_device_diagnostics__single_fan(
    hass: HomeAssistant,
    hass_client: ClientSession,
    config_entry: ConfigEntry,
    config: ConfigType,
) -> None:
    """Test diagnostics for config entry."""
    with patch.object(Helpers, "call_api") as call_api:
        call_api.side_effect = call_api_side_effect__single_fan
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        assert await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "abcdefghabcdefghabcdefghabcdefgh")},
    )
    assert device is not None

    diag = await get_diagnostics_for_device(hass, hass_client, config_entry, device)
    assert isinstance(diag, dict)

    expected_diag = json.loads(
        load_fixture("vesync_async_get_device_diagnostics__single_fan.json", "vesync")
    )
    # not sure how to deal with the dates...
    expected_diag["home_assistant"]["entities"][0]["state"]["last_changed"] = diag[
        "home_assistant"
    ]["entities"][0]["state"]["last_changed"]
    expected_diag["home_assistant"]["entities"][0]["state"]["last_updated"] = diag[
        "home_assistant"
    ]["entities"][0]["state"]["last_updated"]
    expected_diag["home_assistant"]["entities"][1]["state"]["last_changed"] = diag[
        "home_assistant"
    ]["entities"][1]["state"]["last_changed"]
    expected_diag["home_assistant"]["entities"][1]["state"]["last_updated"] = diag[
        "home_assistant"
    ]["entities"][1]["state"]["last_updated"]
    expected_diag["home_assistant"]["entities"][2]["state"]["last_changed"] = diag[
        "home_assistant"
    ]["entities"][2]["state"]["last_changed"]
    expected_diag["home_assistant"]["entities"][2]["state"]["last_updated"] = diag[
        "home_assistant"
    ]["entities"][2]["state"]["last_updated"]

    assert diag == expected_diag
