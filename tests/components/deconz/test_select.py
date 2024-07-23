"""deCONZ select platform tests."""

from collections.abc import Callable
from typing import Any

from pydeconz.models.sensor.presence import (
    PresenceConfigDeviceMode,
    PresenceConfigTriggerDistance,
)
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.test_util.aiohttp import AiohttpClientMocker

TEST_DATA = [
    (  # Presence Device Mode
        {
            "config": {
                "devicemode": "undirected",
                "on": True,
                "reachable": True,
                "sensitivity": 3,
                "triggerdistance": "medium",
            },
            "etag": "13ff209f9401b317987d42506dd4cd79",
            "lastannounced": None,
            "lastseen": "2022-06-28T23:13Z",
            "manufacturername": "aqara",
            "modelid": "lumi.motion.ac01",
            "name": "Aqara FP1",
            "state": {
                "lastupdated": "2022-06-28T23:13:38.577",
                "presence": True,
                "presenceevent": "leave",
            },
            "swversion": "20210121",
            "type": "ZHAPresence",
            "uniqueid": "xx:xx:xx:xx:xx:xx:xx:xx-01-0406",
        },
        {
            "entity_count": 5,
            "device_count": 3,
            "entity_id": "select.aqara_fp1_device_mode",
            "unique_id": "xx:xx:xx:xx:xx:xx:xx:xx-01-0406-device_mode",
            "entity_category": EntityCategory.CONFIG,
            "attributes": {
                "friendly_name": "Aqara FP1 Device Mode",
                "options": ["leftright", "undirected"],
            },
            "option": PresenceConfigDeviceMode.LEFT_AND_RIGHT.value,
            "request": "/sensors/0/config",
            "request_data": {"devicemode": "leftright"},
        },
    ),
    (  # Presence Sensitivity
        {
            "config": {
                "devicemode": "undirected",
                "on": True,
                "reachable": True,
                "sensitivity": 3,
                "triggerdistance": "medium",
            },
            "etag": "13ff209f9401b317987d42506dd4cd79",
            "lastannounced": None,
            "lastseen": "2022-06-28T23:13Z",
            "manufacturername": "aqara",
            "modelid": "lumi.motion.ac01",
            "name": "Aqara FP1",
            "state": {
                "lastupdated": "2022-06-28T23:13:38.577",
                "presence": True,
                "presenceevent": "leave",
            },
            "swversion": "20210121",
            "type": "ZHAPresence",
            "uniqueid": "xx:xx:xx:xx:xx:xx:xx:xx-01-0406",
        },
        {
            "entity_count": 5,
            "device_count": 3,
            "entity_id": "select.aqara_fp1_sensitivity",
            "unique_id": "xx:xx:xx:xx:xx:xx:xx:xx-01-0406-sensitivity",
            "entity_category": EntityCategory.CONFIG,
            "attributes": {
                "friendly_name": "Aqara FP1 Sensitivity",
                "options": ["High", "Medium", "Low"],
            },
            "option": "Medium",
            "request": "/sensors/0/config",
            "request_data": {"sensitivity": 2},
        },
    ),
    (  # Presence Trigger Distance
        {
            "config": {
                "devicemode": "undirected",
                "on": True,
                "reachable": True,
                "sensitivity": 3,
                "triggerdistance": "medium",
            },
            "etag": "13ff209f9401b317987d42506dd4cd79",
            "lastannounced": None,
            "lastseen": "2022-06-28T23:13Z",
            "manufacturername": "aqara",
            "modelid": "lumi.motion.ac01",
            "name": "Aqara FP1",
            "state": {
                "lastupdated": "2022-06-28T23:13:38.577",
                "presence": True,
                "presenceevent": "leave",
            },
            "swversion": "20210121",
            "type": "ZHAPresence",
            "uniqueid": "xx:xx:xx:xx:xx:xx:xx:xx-01-0406",
        },
        {
            "entity_count": 5,
            "device_count": 3,
            "entity_id": "select.aqara_fp1_trigger_distance",
            "unique_id": "xx:xx:xx:xx:xx:xx:xx:xx-01-0406-trigger_distance",
            "entity_category": EntityCategory.CONFIG,
            "attributes": {
                "friendly_name": "Aqara FP1 Trigger Distance",
                "options": ["far", "medium", "near"],
            },
            "option": PresenceConfigTriggerDistance.FAR.value,
            "request": "/sensors/0/config",
            "request_data": {"triggerdistance": "far"},
        },
    ),
]


@pytest.mark.parametrize(("sensor_payload", "expected"), TEST_DATA)
async def test_select(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_setup: ConfigEntry,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    expected: dict[str, Any],
) -> None:
    """Test successful creation of button entities."""
    assert len(hass.states.async_all()) == expected["entity_count"]

    # Verify state data

    button = hass.states.get(expected["entity_id"])
    assert button.attributes == expected["attributes"]

    # Verify entity registry data

    ent_reg_entry = entity_registry.async_get(expected["entity_id"])
    assert ent_reg_entry.entity_category is expected["entity_category"]
    assert ent_reg_entry.unique_id == expected["unique_id"]

    # Verify device registry data

    assert (
        len(
            dr.async_entries_for_config_entry(
                device_registry, config_entry_setup.entry_id
            )
        )
        == expected["device_count"]
    )

    # Verify selecting option
    aioclient_mock = mock_put_request(expected["request"])

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: expected["entity_id"],
            ATTR_OPTION: expected["option"],
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == expected["request_data"]

    # Unload entry

    await hass.config_entries.async_unload(config_entry_setup.entry_id)
    assert hass.states.get(expected["entity_id"]).state == STATE_UNAVAILABLE

    # Remove entry

    await hass.config_entries.async_remove(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
