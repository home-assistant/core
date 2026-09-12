"""Tests for the WattWächter Plus sensor platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aio_wattwaechter import (
    WattwaechterConnectionError,
    WattwaechterError,
    WattwaechterNotFoundError,
    WattwaechterRateLimitError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.wattwaechter.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE_ID, MOCK_METER_DATA_MINIMAL

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test all sensor entities created from a full OBIS payload."""
    with patch("homeassistant.components.wattwaechter.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_minimal_meter_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that only reported OBIS codes create sensors (dynamic)."""
    mock_client.meter_data.return_value = MOCK_METER_DATA_MINIMAL

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    def _get_entity_id(obis_code: str) -> str | None:
        return entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_{obis_code}"
        )

    # Sensors for reported OBIS codes should exist
    assert _get_entity_id("1.8.0") is not None
    assert _get_entity_id("16.7.0") is not None

    # Sensors for unreported OBIS codes should NOT exist
    assert _get_entity_id("2.8.0") is None
    assert _get_entity_id("32.7.0") is None
    assert _get_entity_id("31.7.0") is None


@pytest.mark.parametrize(
    ("obis_code", "device_class", "state_class", "unit", "entity_category"),
    [
        pytest.param(
            "1.7.0",
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
            "W",
            None,
            id="mapped_momentary_unit",
        ),
        pytest.param(
            "15.8.0",
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
            "kWh",
            None,
            id="cumulative_energy",
        ),
        pytest.param(
            "3.8.0",
            SensorDeviceClass.REACTIVE_ENERGY,
            SensorStateClass.TOTAL_INCREASING,
            "kvarh",
            None,
            id="cumulative_reactive_energy",
        ),
        pytest.param(
            "1.6.0",
            None,
            None,
            "kW",
            None,
            id="unmapped_unit_no_statistics",
        ),
        pytest.param(
            "96.1.0",
            None,
            None,
            None,
            EntityCategory.DIAGNOSTIC,
            id="metadata_string",
        ),
        pytest.param(
            "0.2.0",
            None,
            None,
            None,
            EntityCategory.DIAGNOSTIC,
            id="metadata_numeric",
        ),
    ],
)
@pytest.mark.usefixtures("mock_client")
async def test_generic_obis_sensor_classification(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    obis_code: str,
    device_class: SensorDeviceClass | None,
    state_class: SensorStateClass | None,
    unit: str | None,
    entity_category: EntityCategory | None,
) -> None:
    """Test device/state class inference for OBIS codes without a description."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_{obis_code}"
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).entity_category == entity_category

    attributes = hass.states.get(entity_id).attributes
    assert attributes.get("device_class") == device_class
    assert attributes.get("state_class") == state_class
    assert attributes.get("unit_of_measurement") == unit


@pytest.mark.parametrize(
    "error",
    [
        WattwaechterConnectionError("offline"),
        WattwaechterRateLimitError("rate limited"),
        WattwaechterNotFoundError("not found"),
    ],
    ids=["connection", "rate_limit", "not_found"],
)
async def test_system_info_error_is_best_effort(
    hass: HomeAssistant,
    error: WattwaechterError,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a system-info failure keeps meter sensors up; diagnostics go unknown."""
    mock_client.system_info.side_effect = error

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    meter_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_1.8.0"
    )
    assert meter_id is not None
    assert hass.states.get(meter_id).state != STATE_UNAVAILABLE

    ssid_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_ssid"
    )
    assert ssid_id is not None
    assert (
        entity_registry.async_get(ssid_id).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )

    # Diagnostic sensors are disabled by default; enable and reload for a state.
    entity_registry.async_update_entity(ssid_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ssid_id).state == STATE_UNKNOWN


async def test_sensor_value_unknown_when_obis_stops_reporting(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor reports unknown when its OBIS code is no longer reported."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_2.8.0"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state != STATE_UNKNOWN

    # Device stops reporting the export total OBIS code
    mock_client.meter_data.return_value = MOCK_METER_DATA_MINIMAL
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN
