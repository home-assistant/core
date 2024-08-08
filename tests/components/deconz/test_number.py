"""deCONZ number platform tests."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType, WebsocketDataType

from tests.common import snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker

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
            "entity_id": "number.presence_sensor_delay",
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
            "entity_id": "number.presence_sensor_duration",
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


@pytest.mark.parametrize(("sensor_payload", "expected"), TEST_DATA)
async def test_number_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    sensor_ws_data: WebsocketDataType,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    expected: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful creation of number entities."""
    with patch("homeassistant.components.deconz.PLATFORMS", [Platform.NUMBER]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    # Change state

    await sensor_ws_data(expected["websocket_event"])
    assert hass.states.get(expected["entity_id"]).state == expected["next_state"]

    # Verify service calls

    aioclient_mock = mock_put_request("/sensors/0/config")

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
