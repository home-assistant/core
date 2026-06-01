"""Tests for the Infrared websocket API."""

import pytest

from homeassistant.core import HomeAssistant

from .common import MockInfraredEmitterEntity, MockInfraredReceiverEntity

from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("init_infrared")
async def test_list_proxies_empty(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test listing proxies when none are registered."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "infrared/list"})

    response = await client.receive_json()
    assert response["success"] is True
    assert response["result"] == {"proxies": []}


async def test_list_proxies(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test listing the available infrared proxies."""
    # The emitter reports a restricted set of carrier frequencies, the receiver
    # does not report any.
    mock_infrared_emitter_entity._attr_supported_frequencies = [38000, 40000]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "infrared/list"})

    response = await client.receive_json()
    assert response["success"] is True

    proxies = {proxy["entity_id"]: proxy for proxy in response["result"]["proxies"]}
    assert proxies == {
        mock_infrared_emitter_entity.entity_id: {
            "entity_id": mock_infrared_emitter_entity.entity_id,
            "device_id": None,
            "config_entry_id": None,
            "name": "Test IR emitter",
            "type": "emitter",
            "supported_frequencies": [38000, 40000],
        },
        mock_infrared_receiver_entity.entity_id: {
            "entity_id": mock_infrared_receiver_entity.entity_id,
            "device_id": None,
            "config_entry_id": None,
            "name": "Test IR receiver",
            "type": "receiver",
            "supported_frequencies": None,
        },
    }
