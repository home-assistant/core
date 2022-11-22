"""deCONZ select platform tests."""

from unittest.mock import patch

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
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)


async def test_no_select_entities(hass, aioclient_mock):
    """Test that no sensors in deconz results in no sensor entities."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


TEST_DATA = [
    (  # Presence Device Mode
        {
            "sensors": {
                "1": {
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
                }
            }
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
            "request": "/sensors/1/config",
            "request_data": {"devicemode": "leftright"},
        },
    ),
    (  # Presence Sensitivity
        {
            "sensors": {
                "1": {
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
                }
            }
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
            "request": "/sensors/1/config",
            "request_data": {"sensitivity": 2},
        },
    ),
    (  # Presence Trigger Distance
        {
            "sensors": {
                "1": {
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
                }
            }
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
            "request": "/sensors/1/config",
            "request_data": {"triggerdistance": "far"},
        },
    ),
]


@pytest.mark.parametrize("raw_data, expected", TEST_DATA)
async def test_select(hass, aioclient_mock, raw_data, expected):
    """Test successful creation of button entities."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    with patch.dict(DECONZ_WEB_REQUEST, raw_data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == expected["entity_count"]

    # Verify state data

    button = hass.states.get(expected["entity_id"])
    assert button.attributes == expected["attributes"]

    # Verify entity registry data

    ent_reg_entry = ent_reg.async_get(expected["entity_id"])
    assert ent_reg_entry.entity_category is expected["entity_category"]
    assert ent_reg_entry.unique_id == expected["unique_id"]

    # Verify device registry data

    assert (
        len(dr.async_entries_for_config_entry(dev_reg, config_entry.entry_id))
        == expected["device_count"]
    )

    # Verify selecting option

    mock_deconz_put_request(aioclient_mock, config_entry.data, expected["request"])

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

    await hass.config_entries.async_unload(config_entry.entry_id)
    assert hass.states.get(expected["entity_id"]).state == STATE_UNAVAILABLE

    # Remove entry

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
