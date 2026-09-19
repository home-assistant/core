"""Test the ADS entity platforms set up from YAML."""

import struct
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ads.const import DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

BOOL_TRUE = b"\x01"
BOOL_FALSE = b"\x00"


@pytest.mark.parametrize(
    ("platform", "platform_config", "values", "entity_id"),
    [
        pytest.param(
            BINARY_SENSOR_DOMAIN,
            {"adsvar": "GVL.motion", "name": "Motion", "device_class": "motion"},
            {"GVL.motion": BOOL_TRUE},
            "binary_sensor.motion",
            id="binary_sensor",
        ),
        pytest.param(
            SENSOR_DOMAIN,
            {
                "adsvar": "GVL.temperature",
                "name": "Temperature",
                "adstype": "int",
                "factor": 10,
                "device_class": "temperature",
                "state_class": "measurement",
                "unit_of_measurement": "°C",
            },
            {"GVL.temperature": struct.pack("<h", 215)},
            "sensor.temperature",
            id="sensor",
        ),
        pytest.param(
            SWITCH_DOMAIN,
            {"adsvar": "GVL.pump", "name": "Pump"},
            {"GVL.pump": BOOL_TRUE},
            "switch.pump",
            id="switch",
        ),
        pytest.param(
            LIGHT_DOMAIN,
            {
                "adsvar": "GVL.light",
                "adsvar_brightness": "GVL.light_brightness",
                "name": "Ceiling",
            },
            {"GVL.light": BOOL_TRUE, "GVL.light_brightness": struct.pack("<H", 128)},
            "light.ceiling",
            id="light",
        ),
        pytest.param(
            COVER_DOMAIN,
            {
                "adsvar": "GVL.blind_closed",
                "adsvar_position": "GVL.blind_position",
                "adsvar_set_position": "GVL.blind_set_position",
                "name": "Blind",
            },
            {"GVL.blind_closed": BOOL_FALSE, "GVL.blind_position": b"\x4b"},
            "cover.blind",
            id="cover",
        ),
        pytest.param(
            VALVE_DOMAIN,
            {"adsvar": "GVL.valve", "name": "Water"},
            {"GVL.valve": BOOL_TRUE},
            "valve.water",
            id="valve",
        ),
        pytest.param(
            SELECT_DOMAIN,
            {"adsvar": "GVL.mode", "name": "Mode", "options": ["off", "day", "night"]},
            {"GVL.mode": struct.pack("<h", 1)},
            "select.mode",
            id="select",
        ),
    ],
)
async def test_yaml_platform_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ads_notifications: dict[str, bytes],
    snapshot: SnapshotAssertion,
    platform: str,
    platform_config: dict[str, Any],
    values: dict[str, bytes],
    entity_id: str,
) -> None:
    """Test a YAML platform creates its entity and picks up the PLC value."""
    mock_ads_notifications.update(values)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass, platform, {platform: {"platform": DOMAIN, **platform_config}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
    assert state == snapshot
