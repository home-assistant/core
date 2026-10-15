"""Tests for the Radio Frequency websocket API."""

import pytest

from homeassistant.components.radio_frequency import DATA_COMPONENT
from homeassistant.core import HomeAssistant

from . import ENTITY_ID
from .common import MockRadioFrequencyEntity

from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("mock_rf_entity")
async def test_list_transmitters(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing radio frequency transmitters."""
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
        ]
    }


@pytest.mark.usefixtures("init_radio_frequency")
async def test_list_transmitters_empty(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing transmitters when none are registered."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "radio_frequency/list"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"transmitters": []}


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
async def test_list_transmitters_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test listing transmitters is only allowed for admins."""
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id({"type": "radio_frequency/list"})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
