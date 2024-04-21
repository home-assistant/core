"""deCONZ number platform tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_no_number_entities(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that no sensors in deconz results in no number entities."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


TEST_DATA = [
    (  # Presence sensor - delay configuration
        {
            "name": "Presence sensor",
            "type": "ZHAPresence",
            "state": {"dark": False, "presence": False},
            "config": {
                "delay": 0,
                "on": True,
                "reachable": True,
                "temperature": 10,
            },
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        },
        {
            "entity_count": 3,
            "device_count": 3,
            "entity_id": "number.presence_sensor_delay",
            "unique_id": "00:00:00:00:00:00:00:00-00-delay",
            "state": "0",
            "entity_category": EntityCategory.CONFIG,
            "attributes": {
                "min": 0,
                "max": 65535,
                "step": 1,
                "mode": "auto",
                "friendly_name": "Presence sensor Delay",
            },
            "websocket_event": {"config": {"delay": 10}},
            "next_state": "10",
            "supported_service_value": 111,
            "supported_service_response": {"delay": 111},
            "unsupported_service_value": 0.1,
            "unsupported_service_response": {"delay": 0},
            "out_of_range_service_value": 66666,
        },
    ),
    (  # Presence sensor - duration configuration
        {
            "name": "Presence sensor",
            "type": "ZHAPresence",
            "state": {"dark": False, "presence": False},
            "config": {
                "duration": 0,
                "on": True,
                "reachable": True,
                "temperature": 10,
            },
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        },
        {
            "entity_count": 3,
            "device_count": 3,
            "entity_id": "number.presence_sensor_duration",
            "unique_id": "00:00:00:00:00:00:00:00-00-duration",
            "state": "0",
            "entity_category": EntityCategory.CONFIG,
            "attributes": {
                "min": 0,
                "max": 65535,
                "step": 1,
                "mode": "auto",
                "friendly_name": "Presence sensor Duration",
            },
            "websocket_event": {"config": {"duration": 10}},
            "next_state": "10",
            "supported_service_value": 111,
            "supported_service_response": {"duration": 111},
            "unsupported_service_value": 0.1,
            "unsupported_service_response": {"duration": 0},
            "out_of_range_service_value": 66666,
        },
    ),
]


@pytest.mark.parametrize(("sensor_data", "expected"), TEST_DATA)
async def test_number_entities(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_deconz_websocket,
    sensor_data,
    expected,
) -> None:
    """Test successful creation of number entities."""

    with patch.dict(DECONZ_WEB_REQUEST, {"sensors": {"0": sensor_data}}):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == expected["entity_count"]

    # Verify state data

    entity = hass.states.get(expected["entity_id"])
    assert entity.state == expected["state"]
    assert entity.attributes == expected["attributes"]

    # Verify entity registry data

    ent_reg_entry = entity_registry.async_get(expected["entity_id"])
    assert ent_reg_entry.entity_category is expected["entity_category"]
    assert ent_reg_entry.unique_id == expected["unique_id"]

    # Verify device registry data

    assert (
        len(dr.async_entries_for_config_entry(device_registry, config_entry.entry_id))
        == expected["device_count"]
    )

    # Change state

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
    } | expected["websocket_event"]
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()
    assert hass.states.get(expected["entity_id"]).state == expected["next_state"]

    # Verify service calls

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/sensors/0/config")

    # Service set supported value

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: expected["entity_id"],
            ATTR_VALUE: expected["supported_service_value"],
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == expected["supported_service_response"]

    # Service set float value

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: expected["entity_id"],
            ATTR_VALUE: expected["unsupported_service_value"],
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == expected["unsupported_service_response"]

    # Service set value beyond the supported range

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: expected["entity_id"],
                ATTR_VALUE: expected["out_of_range_service_value"],
            },
            blocking=True,
        )

    # Unload entry

    await hass.config_entries.async_unload(config_entry.entry_id)
    assert hass.states.get(expected["entity_id"]).state == STATE_UNAVAILABLE

    # Remove entry

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
