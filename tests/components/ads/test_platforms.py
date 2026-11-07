"""Test the ADS entity platforms set up from YAML."""

import struct
from typing import Any
from unittest.mock import MagicMock, call

import pyads
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ads.const import DATA_ADS, DOMAIN, STATE_KEY_STATE
from homeassistant.components.ads.hub import AdsHub
from homeassistant.components.ads.select import AdsSelect
from homeassistant.components.ads.valve import AdsValve
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.cover import ATTR_POSITION, DOMAIN as COVER_DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_ads_platform

BOOL_TRUE = b"\x01"
BOOL_FALSE = b"\x00"

SELECT_OPTIONS = ["off", "day", "night"]


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
                "adsvar_color_temp_kelvin": "GVL.light_color_temp",
                "min_color_temp_kelvin": 2700,
                "max_color_temp_kelvin": 6500,
                "name": "Ceiling",
            },
            {
                "GVL.light": BOOL_TRUE,
                "GVL.light_brightness": struct.pack("<H", 128),
                "GVL.light_color_temp": struct.pack("<H", 4000),
            },
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
            {"adsvar": "GVL.mode", "name": "Mode", "options": SELECT_OPTIONS},
            {"GVL.mode": struct.pack("<h", 1)},
            "select.mode",
            id="select",
        ),
    ],
)
async def test_yaml_platform_setup(
    hass: HomeAssistant,
    mock_ads_notifications: dict[str, bytes],
    snapshot: SnapshotAssertion,
    platform: str,
    platform_config: dict[str, Any],
    values: dict[str, bytes],
    entity_id: str,
) -> None:
    """Test a YAML platform creates its entity and picks up the PLC value."""
    mock_ads_notifications.update(values)

    assert await setup_ads_platform(
        hass, platform, {"platform": DOMAIN, **platform_config}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
    assert state == snapshot


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


@pytest.mark.parametrize(
    ("platform", "platform_config", "service", "service_data", "entity_id", "writes"),
    [
        pytest.param(
            SWITCH_DOMAIN,
            {"adsvar": "GVL.pump"},
            SERVICE_TURN_ON,
            {},
            "switch.ads_switch",
            [("GVL.pump", True, pyads.PLCTYPE_BOOL)],
            id="switch_turn_on",
        ),
        pytest.param(
            SWITCH_DOMAIN,
            {"adsvar": "GVL.pump"},
            SERVICE_TURN_OFF,
            {},
            "switch.ads_switch",
            [("GVL.pump", False, pyads.PLCTYPE_BOOL)],
            id="switch_turn_off",
        ),
        pytest.param(
            LIGHT_DOMAIN,
            {"adsvar": "GVL.light", "adsvar_brightness": "GVL.light_brightness"},
            SERVICE_TURN_ON,
            {ATTR_BRIGHTNESS: 128},
            "light.ads_light",
            [
                ("GVL.light", True, pyads.PLCTYPE_BOOL),
                ("GVL.light_brightness", 128, pyads.PLCTYPE_UINT),
            ],
            id="light_turn_on_with_brightness",
        ),
        pytest.param(
            LIGHT_DOMAIN,
            {
                "adsvar": "GVL.light",
                "adsvar_color_temp_kelvin": "GVL.light_color_temp",
            },
            SERVICE_TURN_ON,
            {ATTR_COLOR_TEMP_KELVIN: 4000},
            "light.ads_light",
            [
                ("GVL.light", True, pyads.PLCTYPE_BOOL),
                ("GVL.light_color_temp", 4000, pyads.PLCTYPE_UINT),
            ],
            id="light_turn_on_with_color_temp",
        ),
        pytest.param(
            LIGHT_DOMAIN,
            {"adsvar": "GVL.light"},
            SERVICE_TURN_OFF,
            {},
            "light.ads_light",
            [("GVL.light", False, pyads.PLCTYPE_BOOL)],
            id="light_turn_off",
        ),
        pytest.param(
            COVER_DOMAIN,
            {"adsvar": "GVL.blind_closed", "adsvar_open": "GVL.blind_open"},
            SERVICE_OPEN_COVER,
            {},
            "cover.ads_cover",
            [("GVL.blind_open", True, pyads.PLCTYPE_BOOL)],
            id="cover_open",
        ),
        pytest.param(
            COVER_DOMAIN,
            {"adsvar": "GVL.blind_closed", "adsvar_close": "GVL.blind_close"},
            SERVICE_CLOSE_COVER,
            {},
            "cover.ads_cover",
            [("GVL.blind_close", True, pyads.PLCTYPE_BOOL)],
            id="cover_close",
        ),
        pytest.param(
            COVER_DOMAIN,
            {"adsvar": "GVL.blind_closed", "adsvar_stop": "GVL.blind_stop"},
            SERVICE_STOP_COVER,
            {},
            "cover.ads_cover",
            [("GVL.blind_stop", True, pyads.PLCTYPE_BOOL)],
            id="cover_stop",
        ),
        pytest.param(
            COVER_DOMAIN,
            {
                "adsvar": "GVL.blind_closed",
                "adsvar_set_position": "GVL.blind_set_position",
            },
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 75},
            "cover.ads_cover",
            [("GVL.blind_set_position", 75, pyads.PLCTYPE_BYTE)],
            id="cover_set_position",
        ),
        pytest.param(
            COVER_DOMAIN,
            {
                "adsvar": "GVL.blind_closed",
                "adsvar_set_position": "GVL.blind_set_position",
            },
            SERVICE_OPEN_COVER,
            {},
            "cover.ads_cover",
            [("GVL.blind_set_position", 100, pyads.PLCTYPE_BYTE)],
            id="cover_open_without_open_var",
        ),
        pytest.param(
            COVER_DOMAIN,
            {
                "adsvar": "GVL.blind_closed",
                "adsvar_set_position": "GVL.blind_set_position",
            },
            SERVICE_CLOSE_COVER,
            {},
            "cover.ads_cover",
            [("GVL.blind_set_position", 0, pyads.PLCTYPE_BYTE)],
            id="cover_close_without_close_var",
        ),
    ],
)
@pytest.mark.usefixtures("mock_ads_notifications")
async def test_entity_actions_write_to_the_plc(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    platform: str,
    platform_config: dict[str, Any],
    service: str,
    service_data: dict[str, Any],
    entity_id: str,
    writes: list[tuple[str, Any, type]],
) -> None:
    """Test an entity action writes the expected values to the PLC."""
    assert await setup_ads_platform(
        hass, platform, {"platform": DOMAIN, **platform_config}
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        platform, service, {ATTR_ENTITY_ID: entity_id, **service_data}, blocking=True
    )

    assert mock_pyads_connection.return_value.write_by_name.call_args_list == [
        call(*write) for write in writes
    ]


async def test_removing_an_entity_drops_its_subscription(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_notifications: dict[str, bytes],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing an entity unsubscribes it from the still-connected hub.

    Otherwise the hub keeps the notification and its callback, so the PLC goes
    on pushing values for a variable nobody reads and the entity is pinned.
    """
    mock_ads_notifications["GVL.motion"] = BOOL_TRUE

    assert await setup_ads_platform(
        hass,
        BINARY_SENSOR_DOMAIN,
        {"platform": DOMAIN, "adsvar": "GVL.motion", "name": "Motion"},
    )
    await hass.async_block_till_done()

    hub = hass.data[DATA_ADS]
    assert len(hub._notification_items) == 1

    entity_registry.async_update_entity(
        "binary_sensor.motion", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert not hub._notification_items
    mock_pyads_connection.return_value.del_device_notification.assert_called_once()


async def test_renaming_an_entity_keeps_it_subscribed(
    hass: HomeAssistant,
    mock_ads_notifications: dict[str, bytes],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an entity ID change leaves the renamed entity subscribed.

    Home Assistant re-adds the same entity instance after the rename, so the
    removal it does first must not disarm the new subscription.
    """
    mock_ads_notifications["GVL.motion"] = BOOL_TRUE

    assert await setup_ads_platform(
        hass,
        BINARY_SENSOR_DOMAIN,
        {"platform": DOMAIN, "adsvar": "GVL.motion", "name": "Motion"},
    )
    await hass.async_block_till_done()

    entity_registry.async_update_entity(
        "binary_sensor.motion", new_entity_id="binary_sensor.hallway"
    )
    await hass.async_block_till_done()

    hub = hass.data[DATA_ADS]
    assert len(hub._notification_items) == 1
    assert hass.states.get("binary_sensor.hallway").state == STATE_ON
