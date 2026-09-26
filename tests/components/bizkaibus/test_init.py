"""Tests for the Bizkaibus integration setup."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.bizkaibus import sensor
from homeassistant.components.bizkaibus.const import (
    CONF_LINE_IDS,
    CONF_LINES,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.components.bizkaibus.coordinator import BizkaibusUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from tests.common import MockConfigEntry


def _create_coordinator(
    hass: HomeAssistant, entry: MockConfigEntry
) -> BizkaibusUpdateCoordinator:
    """Create a coordinator for sensor tests."""
    return BizkaibusUpdateCoordinator(hass, Mock(), entry)


async def test_setup_platform_imports_yaml(hass: HomeAssistant) -> None:
    """Test importing the legacy YAML configuration."""
    config: ConfigType = {"stopid": "1234", "route": "A"}

    with patch.object(hass.config_entries.flow, "async_init") as mock_async_init:
        await sensor.async_setup_platform(hass, config, Mock())

    mock_async_init.assert_awaited_once_with(
        DOMAIN,
        context={"source": "import"},
        data=config,
    )


async def test_setup_entry_removes_obsolete_entities_and_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing entities and devices for lines no longer selected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STOP_ID: "1234"},
        options={CONF_LINE_IDS: ["A"], CONF_LINES: {"A": "Route A"}},
    )
    entry.add_to_hass(hass)
    coordinator = _create_coordinator(hass, entry)
    entry.runtime_data = coordinator

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "1234")},
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "obsolete",
        config_entry=entry,
        device_id=device.id,
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "1234_A_nearest_arrival",
        config_entry=entry,
        device_id=device.id,
    )

    with patch("homeassistant.components.bizkaibus.BizkaibusAPI") as mock_api_class:
        mock_api_class.return_value.GetTimetable = AsyncMock(return_value=None)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "obsolete") is None
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, "1234_A_nearest_arrival")
        is not None
    )
    assert (
        device_registry.async_get_device_by_identifier((DOMAIN, "1234"), entry.entry_id)
        is not None
    )


async def test_setup_entry_removes_obsolete_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing a device with no remaining entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STOP_ID: "1234"},
        options={CONF_LINE_IDS: [], CONF_LINES: {}},
    )
    entry.add_to_hass(hass)
    coordinator = _create_coordinator(hass, entry)
    entry.runtime_data = coordinator

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "obsolete")},
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "obsolete",
        config_entry=entry,
        device_id=device.id,
    )

    with patch("homeassistant.components.bizkaibus.BizkaibusAPI") as mock_api_class:
        mock_api_class.return_value.GetTimetable = AsyncMock(return_value=None)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "obsolete"), entry.entry_id
        )
        is None
    )
    assert not [state for state in hass.states.async_all() if state.domain == "sensor"]


async def test_sensor_without_config_entry_raises(hass: HomeAssistant) -> None:
    """Test that a sensor requires config entry data."""
    coordinator = Mock(config_entry=None)
    description = sensor.BizkaibusSensorEntityDescription(
        key="nearest_arrival",
        value_fn=lambda arrival: arrival.nearest_arrival,
    )

    with pytest.raises(ValueError, match="Config entry data is empty"):
        sensor.BizkaibusSensor(coordinator, description, "A", "Route A")


async def test_sensor_without_data_is_unavailable(hass: HomeAssistant) -> None:
    """Test a sensor with no coordinator data."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STOP_ID: "1234"})
    entry.add_to_hass(hass)
    coordinator = _create_coordinator(hass, entry)
    coordinator.data = []
    description = sensor.BizkaibusSensorEntityDescription(
        key="nearest_arrival",
        value_fn=lambda arrival: arrival.nearest_arrival,
    )
    entity = sensor.BizkaibusSensor(coordinator, description, "A", "Route A")

    assert entity.native_value is None
    assert entity.extra_state_attributes == {}


async def test_sensor_ignores_unmatched_data(hass: HomeAssistant) -> None:
    """Test a sensor with no matching line data."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STOP_ID: "1234"})
    entry.add_to_hass(hass)
    coordinator = _create_coordinator(hass, entry)
    coordinator.data = [
        SimpleNamespace(bus_id="B", nearest_arrival=None, next_arrival=None)
    ]
    description = sensor.BizkaibusSensorEntityDescription(
        key="nearest_arrival",
        value_fn=lambda arrival: arrival.nearest_arrival,
    )
    entity = sensor.BizkaibusSensor(coordinator, description, "A", "Route A")

    assert entity.native_value is None
    assert entity.extra_state_attributes == {}


async def test_sensor_without_config_entry_in_find_index_raises(
    hass: HomeAssistant,
) -> None:
    """Test that finding a bus requires config entry data."""
    entity = object.__new__(sensor.BizkaibusSensor)
    entity.coordinator = Mock(config_entry=None)

    with pytest.raises(ValueError, match="Config entry data is empty"):
        entity._find_index_by_bus_id()


async def test_setup_entry_creates_sensors(
    hass: HomeAssistant,
) -> None:
    """Test setting up an entry creates one sensor per selected line."""
    arrival_time = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    timetable = SimpleNamespace(
        name="Central Station",
        arrivals={
            "A": SimpleNamespace(
                line=SimpleNamespace(id="A", route="Route A"),
                nearestArrival=SimpleNamespace(GetUTC=arrival_time.isoformat),
                nextArrival=SimpleNamespace(
                    GetUTC=arrival_time.replace(minute=15).isoformat
                ),
            ),
            "B": SimpleNamespace(
                line=SimpleNamespace(id="B", route="Route B"),
                nearestArrival=SimpleNamespace(
                    GetUTC=arrival_time.replace(minute=10).isoformat
                ),
                nextArrival=None,
            ),
        },
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STOP_ID: "1234"},
        options={
            CONF_LINE_IDS: ["A", "B"],
            CONF_LINES: {"A": "Route A", "B": "Route B"},
        },
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.bizkaibus.BizkaibusAPI") as mock_api_class:
        mock_api_class.return_value.GetTimetable = AsyncMock(return_value=timetable)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get("sensor.mock_title_a_route_a").state == arrival_time.isoformat()
    )
    assert (
        hass.states.get("sensor.mock_title_b_route_b").state
        == arrival_time.replace(minute=10).isoformat()
    )
    assert hass.states.get("sensor.mock_title_a_route_a").attributes["attribution"] == (
        "Data provided by Bizkaibus."
    )
    assert hass.states.get("sensor.mock_title_a_route_a").attributes[
        "next_arrival"
    ] == (arrival_time.replace(minute=15))


async def test_setup_entry_without_lines_creates_no_sensors(
    hass: HomeAssistant,
) -> None:
    """Test setting up an entry without selected lines creates no entities."""
    timetable = SimpleNamespace(name=None, arrivals={})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STOP_ID: "1234"},
        options={CONF_LINE_IDS: [], CONF_LINES: {}},
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.bizkaibus.BizkaibusAPI") as mock_api_class:
        mock_api_class.return_value.GetTimetable = AsyncMock(return_value=timetable)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert not [state for state in hass.states.async_all() if state.domain == "sensor"]


async def test_unload_entry(
    hass: HomeAssistant,
) -> None:
    """Test unloading an entry removes its sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STOP_ID: "1234"},
        options={CONF_LINE_IDS: ["A"], CONF_LINES: {"A": "Route A"}},
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.bizkaibus.BizkaibusAPI") as mock_api_class:
        mock_api_class.return_value.GetTimetable = AsyncMock(
            return_value=SimpleNamespace(
                name=None,
                arrivals={
                    "A": SimpleNamespace(
                        line=SimpleNamespace(id="A", route="Route A"),
                        nearestArrival=None,
                        nextArrival=None,
                    )
                },
            )
        )
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.mock_title_a_route_a") is not None
        assert await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get("sensor.mock_title_a_route_a").state == STATE_UNAVAILABLE
