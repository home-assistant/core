"""Tests for the diagnostics data provided by the VeSync integration."""
from unittest.mock import patch

from pyvesync.helpers import Helpers
from syrupy import SnapshotAssertion
from syrupy.matchers import path_type

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

from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_async_get_config_entry_diagnostics__no_devices(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
    config: ConfigType,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    with patch.object(Helpers, "call_api") as call_api:
        call_api.side_effect = call_api_side_effect__no_devices
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert isinstance(diag, dict)
    assert diag == snapshot


async def test_async_get_config_entry_diagnostics__single_humidifier(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
    config: ConfigType,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    with patch.object(Helpers, "call_api") as call_api:
        call_api.side_effect = call_api_side_effect__single_humidifier
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert isinstance(diag, dict)
    assert diag == snapshot


async def test_async_get_device_diagnostics__single_fan(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
    config: ConfigType,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    with patch.object(Helpers, "call_api") as call_api:
        call_api.side_effect = call_api_side_effect__single_fan
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "abcdefghabcdefghabcdefghabcdefgh")},
    )
    assert device is not None

    diag = await get_diagnostics_for_device(hass, hass_client, config_entry, device)

    assert isinstance(diag, dict)
    diag["home_assistant"]["entities"] = sorted(
        diag["home_assistant"]["entities"], key=lambda ent: ent["entity_id"]
    )
    assert diag == snapshot(
        matcher=path_type(
            {
                "home_assistant.entities.0.state.last_changed": (str,),
                "home_assistant.entities.0.state.last_updated": (str,),
                "home_assistant.entities.1.state.last_changed": (str,),
                "home_assistant.entities.1.state.last_updated": (str,),
                "home_assistant.entities.2.state.last_changed": (str,),
                "home_assistant.entities.2.state.last_updated": (str,),
            }
        )
    )
