"""Test the Silla Prism sensors."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import fire_burst, setup_integration

from tests.common import MockConfigEntry, async_fire_mqtt_message, snapshot_platform
from tests.typing import MqttMockHAClient

ERROR_ENTITY_ID = "sensor.silla_prism_error"
ERROR_TOPIC = "prism/1/error"
POWER_ENTITY_ID = "sensor.silla_prism_power"
POWER_TOPIC = "prism/1/w"
SESSION_START_ENTITY_ID = "sensor.silla_prism_session_start"
SESSION_TIME_TOPIC = "prism/1/session_time"


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
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mqtt_mock")
async def test_undocumented_error_code(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that an error code outside the documented ones reads as unknown."""
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    async_fire_mqtt_message(hass, ERROR_TOPIC, "12")
    await hass.async_block_till_done()

    assert hass.states.get(ERROR_ENTITY_ID).state == STATE_UNKNOWN
    assert caplog.text.count("Unknown error code: 12") == 1

    async_fire_mqtt_message(hass, ERROR_TOPIC, "12")
    await hass.async_block_till_done()

    assert caplog.text.count("Unknown error code: 12") == 1

    async_fire_mqtt_message(hass, ERROR_TOPIC, "0")
    async_fire_mqtt_message(hass, POWER_TOPIC, "2000.0")
    await hass.async_block_till_done()

    assert hass.states.get(ERROR_ENTITY_ID).state == "none"
    assert hass.states.get(POWER_ENTITY_ID).state == "2000.0"


@pytest.mark.usefixtures("mqtt_mock")
@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        pytest.param("16089", "2025-12-31T19:32:50+00:00", id="jitter_ignored"),
        pytest.param("16150", "2025-12-31T19:31:50+00:00", id="new_session_tracked"),
    ],
)
async def test_session_start_deviation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    elapsed: str,
    expected: str,
) -> None:
    """Test the session start absorbs jitter but follows a real change."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    assert hass.states.get(SESSION_START_ENTITY_ID).state == "2025-12-31T19:32:50+00:00"

    freezer.tick(timedelta(seconds=60))
    async_fire_mqtt_message(hass, SESSION_TIME_TOPIC, elapsed)
    await hass.async_block_till_done()

    assert hass.states.get(SESSION_START_ENTITY_ID).state == expected


@pytest.mark.usefixtures("mqtt_mock")
async def test_session_start_without_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that no running session reads as unknown."""
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    async_fire_mqtt_message(hass, SESSION_TIME_TOPIC, "0")
    await hass.async_block_till_done()

    assert hass.states.get(SESSION_START_ENTITY_ID).state == STATE_UNKNOWN
