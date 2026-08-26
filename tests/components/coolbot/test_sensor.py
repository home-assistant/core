"""Sensor entities: values, availability, and dynamic device handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from homeassistant.components.coolbot.const import UPDATE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import setup_integration
from .conftest import make_device

from tests.common import MockConfigEntry, async_fire_time_changed


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    # Assert wire values as-is rather than through metric conversion.
    hass.config.units = US_CUSTOMARY_SYSTEM
    assert await setup_integration(hass, entry)


async def _tick(hass: HomeAssistant) -> None:
    async_fire_time_changed(
        hass, dt_util.utcnow() + UPDATE_INTERVAL + timedelta(seconds=1)
    )
    await hass.async_block_till_done()


async def test_sensor_values(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Each description surfaces the right field from the device."""
    await _setup(hass, mock_config_entry)

    assert hass.states.get("sensor.walk_in_cooler_room_temperature").state == "38.5"
    assert hass.states.get("sensor.walk_in_cooler_fin_temperature").state == "30.2"
    assert hass.states.get("sensor.walk_in_cooler_set_point").state == "40.0"
    assert hass.states.get("sensor.walk_in_cooler_hardware_status").state == "Cooling"


async def test_wifi_signal_is_disabled_by_default(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """The diagnostic signal sensor registers but stays disabled."""
    await _setup(hass, mock_config_entry)

    assert hass.states.get("sensor.walk_in_cooler_wi_fi_signal") is None
    registry = er.async_get(hass)
    entry = registry.async_get_entity_id(
        "sensor", "coolbot", "coolbot_aabbccddeeff_wifi_signal"
    )
    assert entry is not None  # registered, just not enabled


async def test_unprovisioned_slots_create_no_entities(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Empty device slots must not publish believable-looking temperatures."""
    mock_client.async_get_devices.return_value = [
        make_device(),
        make_device(
            unique_id="coolbot_10_1",
            name="Empty slot",
            is_provisioned=False,
            mac_address=None,
        ),
    ]
    await _setup(hass, mock_config_entry)

    assert hass.states.get("sensor.walk_in_cooler_room_temperature") is not None
    assert hass.states.get("sensor.empty_slot_room_temperature") is None


async def test_stale_measurements_go_unavailable_but_settings_stay(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Measurements go unavailable when stale; settings remain readable."""
    await _setup(hass, mock_config_entry)
    assert hass.states.get("sensor.walk_in_cooler_room_temperature").state == "38.5"

    mock_client.async_get_devices.return_value = [
        make_device(
            last_data_at=datetime.now(UTC) - timedelta(minutes=10), status="OFFLINE"
        )
    ]
    await _tick(hass)

    # The cloud would keep serving 38.5 forever; reporting it would be a lie.
    assert (
        hass.states.get("sensor.walk_in_cooler_room_temperature").state == "unavailable"
    )
    # A set point is configuration, still true while the box is offline.
    assert hass.states.get("sensor.walk_in_cooler_set_point").state == "40.0"


async def test_a_cooler_added_later_appears_without_a_reload(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """New coolers on the account appear on the next refresh."""
    await _setup(hass, mock_config_entry)
    assert hass.states.get("sensor.cellar_room_temperature") is None

    mock_client.async_get_devices.return_value = [
        make_device(),
        make_device(unique_id="coolbot_112233445566", name="Cellar"),
    ]
    await _tick(hass)

    state = hass.states.get("sensor.cellar_room_temperature")
    assert state is not None
    assert state.state == "38.5"


async def test_entities_survive_a_device_missing_from_one_refresh(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A device absent from one refresh goes unavailable, not deleted."""
    await _setup(hass, mock_config_entry)

    mock_client.async_get_devices.return_value = [
        make_device(unique_id="coolbot_other", name="Other")
    ]
    await _tick(hass)

    state = hass.states.get("sensor.walk_in_cooler_room_temperature")
    assert state is not None
    assert state.state == "unavailable"
