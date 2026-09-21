"""Test the ADS entity platforms set up from YAML."""

import struct
from typing import Any
from unittest.mock import MagicMock

import pyads
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ads.const import DOMAIN, STATE_KEY_STATE
from homeassistant.components.ads.hub import AdsHub
from homeassistant.components.ads.select import AdsSelect
from homeassistant.components.ads.valve import AdsValve
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


@pytest.mark.usefixtures("mock_ads_notifications")
async def test_rejected_entity_is_not_left_on_the_hub(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entity the platform refuses to add does not stay on the hub.

    Both entries share an ADS variable, so the second one is rejected for a
    duplicate unique ID and must not be resubscribed on the next reload.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: [
                {"platform": DOMAIN, "adsvar": "GVL.motion", "name": "Motion"},
                {"platform": DOMAIN, "adsvar": "GVL.motion", "name": "Motion copy"},
            ]
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.motion_copy") is None
    assert len(mock_config_entry.runtime_data.devices) == 1


SELECT_OPTIONS = ["off", "day", "night"]


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        pytest.param(None, None, id="no_value_yet"),
        pytest.param(0, "off", id="first_option"),
        pytest.param(2, "night", id="last_option"),
        pytest.param(3, None, id="out_of_range"),
    ],
)
def test_select_option_follows_the_plc(state: int | None, expected: str | None) -> None:
    """Test the selected option is derived from the value the PLC reports."""
    entity = AdsSelect(MagicMock(spec=AdsHub), "GVL.mode", "Mode", SELECT_OPTIONS)
    entity._state_dict[STATE_KEY_STATE] = state

    assert entity.current_option == expected


def test_select_option_writes_the_index() -> None:
    """Test selecting an option writes its index to the PLC."""
    hub = MagicMock(spec=AdsHub)
    entity = AdsSelect(hub, "GVL.mode", "Mode", SELECT_OPTIONS)

    entity.select_option("night")

    hub.write_by_name.assert_called_once_with("GVL.mode", 2, pyads.PLCTYPE_INT)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        pytest.param(None, None, id="no_value_yet"),
        pytest.param(True, False, id="open"),
        pytest.param(False, True, id="closed"),
    ],
)
def test_valve_state_follows_the_plc(state: bool | None, expected: bool | None) -> None:
    """Test the valve state is derived from the value the PLC reports."""
    entity = AdsValve(MagicMock(spec=AdsHub), "GVL.valve", "Water", None)
    entity._state_dict[STATE_KEY_STATE] = state

    assert entity.is_closed == expected


@pytest.mark.parametrize(
    ("action", "written"),
    [
        pytest.param("open_valve", True, id="open"),
        pytest.param("close_valve", False, id="close"),
    ],
)
def test_valve_actions_write_to_the_plc(action: str, written: bool) -> None:
    """Test opening and closing the valve writes to the PLC."""
    hub = MagicMock(spec=AdsHub)
    entity = AdsValve(hub, "GVL.valve", "Water", None)

    getattr(entity, action)()

    hub.write_by_name.assert_called_once_with("GVL.valve", written, pyads.PLCTYPE_BOOL)
