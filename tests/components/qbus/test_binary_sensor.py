"""Test Qbus binary sensors."""

from collections.abc import Awaitable, Callable
import json
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_binary_sensor(
    hass: HomeAssistant,
    setup_integration_deferred: Callable[[], Awaitable],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor."""

    with patch("homeassistant.components.qbus.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration_deferred()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize("property_name", ["raining", "twilight"])
@pytest.mark.parametrize(
    ("on_value", "off_value"),
    [
        pytest.param(True, False, id="boolean"),
        pytest.param("true", "false", id="string"),
        pytest.param("TRUE", "FALSE", id="uppercase-string"),
        pytest.param("true", False, id="boolean-off"),
    ],
)
async def test_weather_binary_sensor_state(
    hass: HomeAssistant,
    property_name: str,
    on_value: bool | str,
    off_value: bool | str,
) -> None:
    """Test weather states and partial updates for boolean and string payloads."""
    entity_id = f"binary_sensor.tuin_weersensor_{property_name}"
    topic = "cloudapp/QBUSMQTTGW/UL1/UL60/state"

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(
            {"id": "UL60", "properties": {property_name: on_value}, "type": "event"}
        ),
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"

    async_fire_mqtt_message(
        hass, topic, '{"id":"UL60","properties":{"wind":25},"type":"event"}'
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(
            {"id": "UL60", "properties": {property_name: off_value}, "type": "event"}
        ),
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "off"
