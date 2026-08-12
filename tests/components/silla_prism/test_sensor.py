"""Test the Silla Prism sensors."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import fire_burst, setup_integration

from tests.common import MockConfigEntry, async_fire_mqtt_message, snapshot_platform
from tests.typing import MqttMockHAClient

ERROR_ENTITY_ID = "sensor.silla_prism_error"


async def test_sensors(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors."""
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mqtt_mock")
async def test_undocumented_error_code(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an error code outside the documented ones reads as unknown."""
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    async_fire_mqtt_message(hass, "prism/1/error", "12")
    await hass.async_block_till_done()

    assert hass.states.get(ERROR_ENTITY_ID).state == STATE_UNKNOWN
