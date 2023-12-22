"""deCONZ button platform tests."""
from unittest.mock import patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_no_binary_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that no sensors in deconz results in no sensor entities."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


TEST_DATA = [
    (  # Store scene button
        {
            "groups": {
                "1": {
                    "id": "Light group id",
                    "name": "Light group",
                    "type": "LightGroup",
                    "state": {"all_on": False, "any_on": True},
                    "action": {},
                    "scenes": [{"id": "1", "name": "Scene"}],
                    "lights": [],
                }
            }
        },
        {
            "entity_count": 2,
            "device_count": 3,
            "entity_id": "button.light_group_scene_store_current_scene",
            "unique_id": "01234E56789A/groups/1/scenes/1-store",
            "entity_category": EntityCategory.CONFIG,
            "attributes": {
                "icon": "mdi:inbox-arrow-down",
                "friendly_name": "Light group Scene Store Current Scene",
            },
            "request": "/groups/1/scenes/1/store",
            "request_data": {},
        },
    ),
    (  # Presence reset button
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
            "entity_id": "button.aqara_fp1_reset_presence",
            "unique_id": "xx:xx:xx:xx:xx:xx:xx:xx-01-0406-reset_presence",
            "entity_category": EntityCategory.CONFIG,
            "attributes": {
                "device_class": "restart",
                "friendly_name": "Aqara FP1 Reset Presence",
            },
            "request": "/sensors/1/config",
            "request_data": {"resetpresence": True},
        },
    ),
]


@pytest.mark.parametrize(("raw_data", "expected"), TEST_DATA)
async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    aioclient_mock: AiohttpClientMocker,
    raw_data,
    expected,
) -> None:
    """Test successful creation of button entities."""
    with patch.dict(DECONZ_WEB_REQUEST, raw_data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

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
        len(dr.async_entries_for_config_entry(device_registry, config_entry.entry_id))
        == expected["device_count"]
    )

    # Verify button press

    mock_deconz_put_request(aioclient_mock, config_entry.data, expected["request"])

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: expected["entity_id"]},
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
