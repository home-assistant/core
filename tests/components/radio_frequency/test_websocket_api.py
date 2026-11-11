"""Tests for the Radio Frequency websocket API."""

import pytest
from pytest_homeassistant.components.radio_frequency import (
    ENTITY_ID,
    RECEIVER_ENTITY_ID,
)
from pytest_homeassistant.components.radio_frequency.common import (
    MockRadioFrequencyEntity,
)
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.radio_frequency import DATA_COMPONENT
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("mock_rf_entity", "mock_rf_receiver_entity")
async def test_list_entities(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing radio frequency transmitters and receivers."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "radio_frequency/list"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "transmitters": [
            {
                "entity_id": ENTITY_ID,
                "device_id": None,
                "config_entry_id": None,
                "supported_frequency_ranges": [[433_000_000, 434_000_000]],
                "supported_modulations": ["OOK"],
            }
        ],
        "receivers": [
            {
                "entity_id": RECEIVER_ENTITY_ID,
                "device_id": None,
                "config_entry_id": None,
                "supported_frequency_ranges": [[433_000_000, 434_000_000]],
                "supported_modulations": ["OOK"],
            }
        ],
    }


@pytest.mark.usefixtures("init_radio_frequency")
async def test_list_entities_empty(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing entities when none are registered."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "radio_frequency/list"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"transmitters": [], "receivers": []}


@pytest.mark.usefixtures("init_radio_frequency")
async def test_list_multiple_transmitters_with_ranges(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing transmitters reports each one's supported frequency ranges."""
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities(
        [
            MockRadioFrequencyEntity(
                "transmitter_one",
                frequency_ranges=[(433_000_000, 434_000_000)],
            ),
            MockRadioFrequencyEntity(
                "transmitter_two",
                frequency_ranges=[
                    (868_000_000, 868_500_000),
                    (915_000_000, 928_000_000),
                ],
            ),
        ]
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "radio_frequency/list"})
    response = await client.receive_json()

    assert response["success"]
    transmitters = response["result"]["transmitters"]
    assert len(transmitters) == 2
    all_ranges = [
        transmitter["supported_frequency_ranges"] for transmitter in transmitters
    ]
    assert [[433_000_000, 434_000_000]] in all_ranges
    assert [[868_000_000, 868_500_000], [915_000_000, 928_000_000]] in all_ranges


@pytest.mark.usefixtures("mock_rf_entity")
async def test_list_entities_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test listing entities is only allowed for admins."""
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id({"type": "radio_frequency/list"})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
