"""Test the rtl_433 sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pyrtl_433.normalizer import NormalizedEvent
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import emit_event, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
    mock_event: NormalizedEvent,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test one sensor entity is created per measurement field of a device."""
    with patch("homeassistant.components.rtl_433.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

        # No entities exist until the device first transmits.
        assert not er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )

        await emit_event(hass, mock_rtl433_client, mock_event)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_value_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
    mock_event: NormalizedEvent,
) -> None:
    """Test a subsequent event updates the sensor's native value."""
    await setup_integration(hass, mock_config_entry)
    await emit_event(hass, mock_rtl433_client, mock_event)

    assert hass.states.get("sensor.acurite_606tx_temperature_c").state == "21.5"

    await emit_event(
        hass,
        mock_rtl433_client,
        NormalizedEvent(
            device_key="Acurite-606TX-42",
            model="Acurite-606TX",
            identity={"model": "Acurite-606TX", "id": 42},
            fields={"temperature_C": 19.0, "battery_ok": 1},
        ),
    )

    assert hass.states.get("sensor.acurite_606tx_temperature_c").state == "19.0"
