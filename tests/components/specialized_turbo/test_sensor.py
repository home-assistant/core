"""Tests for Specialized Turbo sensor entities."""

from datetime import timedelta
import logging
import time
from unittest.mock import MagicMock, patch

from bleak import BleakError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.specialized_turbo.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import (
    MOCK_ADDRESS_FORMATTED,
    MOCK_MANUFACTURER_DATA,
    TCX_SERVICE_INFO,
    MockLibrary,
    make_populated_snapshot,
    make_service_info,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)


def _entity_id(entity_registry: er.EntityRegistry, key: str) -> str:
    """Return an entity ID from its stable integration unique ID."""
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{MOCK_ADDRESS_FORMATTED}_{key}",
    )
    assert entity_id is not None
    return entity_id


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensor metadata and values."""
    mock_library.monitor.snapshot = make_populated_snapshot()
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


async def test_sensors_unavailable_before_first_message(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensors remain unavailable before telemetry arrives."""
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)

    state = hass.states.get(_entity_id(entity_registry, "battery_charge_percent"))
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_notification_updates_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a library notification updates entity state."""
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)
    updated = make_populated_snapshot()

    callback = mock_library.monitor.on_update
    assert callable(callback)
    callback(MagicMock(), updated)
    await hass.async_block_till_done()

    battery = hass.states.get(_entity_id(entity_registry, "battery_charge_percent"))
    speed = hass.states.get(_entity_id(entity_registry, "speed"))
    assist = hass.states.get(_entity_id(entity_registry, "assist_level"))
    assert battery is not None
    assert speed is not None
    assert assist is not None
    assert battery.state == "85"
    assert speed.state == "25.5"
    assert assist.state == "trail"


async def test_disconnect_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a library disconnect and reconnect update availability."""
    mock_library.monitor.snapshot = make_populated_snapshot()
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)
    battery_entity_id = _entity_id(entity_registry, "battery_charge_percent")
    battery = hass.states.get(battery_entity_id)
    assert battery is not None
    assert battery.state == "85"

    disconnect_callback = mock_library.connection_constructor.call_args.kwargs[
        "disconnect_callback"
    ]
    with caplog.at_level(logging.INFO):
        mock_library.connection.is_connected = False
        disconnect_callback(mock_library.connection)
        await hass.async_block_till_done()

        battery = hass.states.get(battery_entity_id)
        assert battery is not None
        assert battery.state == STATE_UNAVAILABLE

        with patch(
            "homeassistant.components.bluetooth.manager.discovery_flow.async_create_flow"
        ):
            inject_bluetooth_service_info(
                hass,
                make_service_info(
                    manufacturer_data={
                        **MOCK_MANUFACTURER_DATA,
                        0xFFFF: b"\x01",
                    }
                ),
            )
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
        await hass.async_block_till_done()

        battery = hass.states.get(battery_entity_id)
        assert battery is not None
        assert battery.state == "85"
        assert (
            caplog.text.count(
                "Specialized Turbo at DC:DD:BB:4A:D6:55 is available again"
            )
            == 1
        )


async def test_stale_advertisement_keeps_connected_entities_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test Bluetooth expiry does not override an active GATT connection."""
    start_monotonic = time.monotonic()
    mock_library.monitor.snapshot = make_populated_snapshot()
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)
    battery_entity_id = _entity_id(entity_registry, "battery_charge_percent")

    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1
    with caplog.at_level(logging.INFO):
        with (
            patch_bluetooth_time(monotonic_now),
            patch_all_discovered_devices([]),
        ):
            async_fire_time_changed(
                hass,
                dt_util.utcnow()
                + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
            )
            await hass.async_block_till_done()

        battery = hass.states.get(battery_entity_id)
        assert battery is not None
        assert battery.state == "85"
        assert mock_library.connection.is_connected is True
        assert "is unavailable" not in caplog.text


async def test_stale_advertisement_logs_failed_connection_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test advertisement expiry logs an unavailable disconnected bike once."""
    start_monotonic = time.monotonic()
    mock_library.connection.connect.side_effect = BleakError("failed")
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)

    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1
    with (
        caplog.at_level(logging.INFO),
        patch_bluetooth_time(monotonic_now),
        patch_all_discovered_devices([]),
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    assert (
        caplog.text.count("Specialized Turbo at DC:DD:BB:4A:D6:55 is unavailable") == 1
    )


@pytest.mark.parametrize("assist_level", [None, 99])
async def test_unknown_assist_level(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    entity_registry: er.EntityRegistry,
    assist_level: int | None,
) -> None:
    """Test an unknown assist value produces an unknown entity state."""
    snapshot = make_populated_snapshot()
    snapshot.motor.assist_level = assist_level
    mock_library.monitor.snapshot = snapshot
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)

    assist = hass.states.get(_entity_id(entity_registry, "assist_level"))
    assert assist is not None
    assert assist.state == STATE_UNKNOWN
