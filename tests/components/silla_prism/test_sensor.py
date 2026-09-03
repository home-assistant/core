"""Test the Silla Prism sensors."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.silla_prism.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import fire_burst, setup_integration

from tests.common import MockConfigEntry, async_fire_mqtt_message, snapshot_platform
from tests.typing import MqttMockHAClient

ERROR_TOPIC = "prism/1/error"
POWER_TOPIC = "prism/1/w"
SESSION_TIME_TOPIC = "prism/1/session_time"


def _entity_id(
    entity_registry: er.EntityRegistry, platform: Platform, unique_id: str
) -> str:
    entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_sensors(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensors."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    with patch("homeassistant.components.silla_prism.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mqtt_mock")
async def test_error_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that Prism error values update the problem binary sensor."""
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    async_fire_mqtt_message(hass, ERROR_TOPIC, "12")
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    error_entity_id = _entity_id(
        entity_registry, Platform.BINARY_SENSOR, "prism_error_001"
    )
    state = hass.states.get(error_entity_id)
    assert state is not None
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, ERROR_TOPIC, "0")
    async_fire_mqtt_message(hass, POWER_TOPIC, "2000.0")
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    power_entity_id = _entity_id(
        entity_registry, Platform.SENSOR, "prism_output_power_001"
    )
    state = hass.states.get(error_entity_id)
    assert state is not None
    assert state.state == STATE_OFF
    state = hass.states.get(power_entity_id)
    assert state is not None
    assert state.state == "2000.0"


@pytest.mark.usefixtures("mqtt_mock")
@pytest.mark.parametrize("elapsed", ["16089", "16150"])
async def test_session_time_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    elapsed: str,
) -> None:
    """Test the session time sensor follows Prism session_time payloads."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    session_time_entity_id = _entity_id(
        entity_registry, Platform.SENSOR, "prism_session_time_001"
    )
    state = hass.states.get(session_time_entity_id)
    assert state is not None
    assert state.state == "16030"

    freezer.tick(timedelta(seconds=60))
    async_fire_mqtt_message(hass, SESSION_TIME_TOPIC, elapsed)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get(session_time_entity_id)
    assert state is not None
    assert state.state == elapsed


@pytest.mark.usefixtures("mqtt_mock")
async def test_session_time_without_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that no running session reads as zero seconds."""
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    async_fire_mqtt_message(hass, SESSION_TIME_TOPIC, "0")
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    session_time_entity_id = _entity_id(
        entity_registry, Platform.SENSOR, "prism_session_time_001"
    )
    state = hass.states.get(session_time_entity_id)
    assert state is not None
    assert state.state == "0"
