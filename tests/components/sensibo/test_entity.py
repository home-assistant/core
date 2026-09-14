"""The test for the sensibo entity."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pysensibo.model import SensiboData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
)
from homeassistant.components.sensibo.const import DOMAIN, SENSIBO_ERRORS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from tests.common import async_fire_time_changed


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    load_int: ConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Sensibo device."""

    state1 = hass.states.get("climate.hallway_hallway")
    assert state1

    device_entries = dr.async_entries_for_config_entry(
        device_registry, load_int.entry_id
    )
    device_entries.sort(key=lambda d: d.name)
    assert device_entries == snapshot


@pytest.mark.parametrize("load_platforms", [[Platform.BINARY_SENSOR]])
@pytest.mark.usefixtures("hass")
async def test_motion_sensor_via_device(
    device_registry: dr.DeviceRegistry,
    load_int: ConfigEntry,
) -> None:
    """Test the motion sensor is linked to its parent device.

    Only the binary sensor platform is loaded so that the parent device is
    solely registered during setup, guarding against the child resolving its
    via_device_id before the parent exists.
    """
    parent_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "ABC999111"), load_int.entry_id
    )
    assert parent_device
    motion_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "AABBCC"), load_int.entry_id
    )
    assert motion_device
    assert motion_device.via_device_id == parent_device.id


@pytest.mark.parametrize("load_platforms", [[Platform.BINARY_SENSOR]])
async def test_motion_sensor_via_device_dynamic_add(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    get_data: tuple[SensiboData, dict[str, Any], dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the motion sensor links to its parent when added at runtime.

    Only the binary sensor platform is loaded, so the parent AC device is
    registered solely by the integration, never by a climate entity. The parent
    is removed and re-added via a coordinator update to exercise the dynamic-add
    path, where the motion sensor must still resolve its parent's via_device_id.
    """
    new_result = [
        device for device in get_data[2]["result"] if device["id"] != "ABC999111"
    ]
    new_parsed = {k: v for k, v in get_data[0].parsed.items() if k != "ABC999111"}
    mock_client.async_get_devices.return_value = {
        "status": "success",
        "result": new_result,
    }
    mock_client.async_get_devices_data.return_value = SensiboData(
        new_result, new_parsed
    )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, "ABC999111"), load_int.entry_id
    )
    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, "AABBCC"), load_int.entry_id
    )

    mock_client.async_get_devices.return_value = get_data[2]
    mock_client.async_get_devices_data.return_value = get_data[0]

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    parent_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "ABC999111"), load_int.entry_id
    )
    assert parent_device
    motion_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "AABBCC"), load_int.entry_id
    )
    assert motion_device
    assert motion_device.via_device_id == parent_device.id


@pytest.mark.parametrize("p_error", SENSIBO_ERRORS)
async def test_entity_failed_service_calls(
    hass: HomeAssistant,
    p_error: Exception,
    load_int: ConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the Sensibo send command with error."""

    state = hass.states.get("climate.hallway_hallway")
    assert state

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Success"}
    }

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_FAN_MODE: "low"},
        blocking=True,
    )

    state = hass.states.get("climate.hallway_hallway")
    assert state.attributes["fan_mode"] == "low"

    mock_client.async_set_ac_state_property.side_effect = p_error

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_FAN_MODE: "low"},
            blocking=True,
        )

    state = hass.states.get("climate.hallway_hallway")
    assert state.attributes["fan_mode"] == "low"
