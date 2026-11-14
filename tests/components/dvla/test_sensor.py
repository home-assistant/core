"""Tests for the DVLA sensor platform."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.dvla.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import STATE_UNKNOWN, UnitOfVolume
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.util.json import JsonObjectType


def get_entity_id(entity_registry: er.EntityRegistry, key: str) -> str:
    """Get entity ID by DVLA sensor key."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"AB12CDE-{key}",
    )

    assert entity_id is not None
    return entity_id


def get_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    key: str,
) -> State:
    """Get state by DVLA sensor key."""
    state = hass.states.get(get_entity_id(entity_registry, key))

    assert state is not None
    return state


@pytest.mark.parametrize(
    ("key", "data"),
    [
        pytest.param("taxStatus", {"taxStatus": "Unexpected"}, id="invalid-tax-status"),
        pytest.param(
            "revenueWeight", {"revenueWeight": "not-a-number"}, id="invalid-weight"
        ),
        pytest.param("taxDueDate", {"taxDueDate": "not-a-date"}, id="invalid-date"),
        pytest.param("taxDueDate", {"taxDueDate": 123}, id="non-string-date"),
        pytest.param(
            "monthOfFirstRegistration",
            {"monthOfFirstDvlaRegistration": "2024-05"},
            id="dvla-registration-month-is-not-a-substitute",
        ),
    ],
)
async def test_unknown_sensor_value(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
    key: str,
    data: dict[str, int | str],
) -> None:
    """Test absent or invalid values are exposed as unknown."""
    await setup_dvla_entry({"registrationNumber": "AB12CDE", "make": "FORD", **data})

    assert get_state(hass, entity_registry, key).state == STATE_UNKNOWN


async def test_sensor_platform(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    setup_dvla_entry: Callable[
        [dict[str, Any] | None],
        Awaitable[MockConfigEntry],
    ],
) -> None:
    """Test sensor platform setup."""
    entry = await setup_dvla_entry()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_no_engine_capacity_for_electric_vehicle(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
) -> None:
    """Test an electric vehicle without engine capacity does not get that sensor."""
    await setup_dvla_entry(
        {"registrationNumber": "AB12CDE", "make": "FORD", "fuelType": "ELECTRICITY"}
    )

    assert (
        entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            "AB12CDE-engineCapacity",
        )
        is None
    )
    assert get_state(hass, entity_registry, "fuelType").state == "ELECTRICITY"


async def test_engine_capacity_unit_conversion(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
) -> None:
    """Test engine capacity can be displayed in litres."""
    await setup_dvla_entry()

    entity_registry.async_update_entity_options(
        get_entity_id(entity_registry, "engineCapacity"),
        "sensor",
        {"unit_of_measurement": UnitOfVolume.LITERS},
    )
    await hass.async_block_till_done()

    state = get_state(hass, entity_registry, "engineCapacity")
    assert float(state.state) == pytest.approx(1.998)
    assert state.attributes["unit_of_measurement"] == UnitOfVolume.LITERS


async def test_revenue_weight_sensor_is_numeric(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
) -> None:
    """Test revenue weight is exposed as a numeric weight sensor."""
    await setup_dvla_entry(
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "revenueWeight": "3500",
        },
    )

    state = get_state(hass, entity_registry, "revenueWeight")

    assert state.state == "3500"
    assert state.attributes["unit_of_measurement"] == "kg"
    assert state.attributes["device_class"] == SensorDeviceClass.WEIGHT


async def test_sensor_updates_after_weekly_refresh(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_dvla_client: AsyncMock,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
    vehicle_data: JsonObjectType,
) -> None:
    """Test weekly polling updates sensors, including newly returned values."""
    initial_data = vehicle_data.copy()
    initial_data.pop("motExpiryDate")
    mock_dvla_client.side_effect = [
        initial_data,
        {**vehicle_data, "taxStatus": "Untaxed"},
    ]
    await setup_dvla_entry()

    assert get_state(hass, entity_registry, "taxStatus").state == "taxed"
    assert get_state(hass, entity_registry, "motExpiryDate").state == STATE_UNKNOWN

    freezer.tick(timedelta(days=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_dvla_client.assert_awaited_once()

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_dvla_client.await_count == 2
    assert get_state(hass, entity_registry, "taxStatus").state == "untaxed"
    assert (
        get_state(hass, entity_registry, "motExpiryDate").state
        == vehicle_data["motExpiryDate"]
    )


async def test_device_entry_type(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
) -> None:
    """Test DVLA device is marked as a service."""
    entry = await setup_dvla_entry()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "AB12CDE"),
        entry.entry_id,
    )

    assert device is not None
    assert device.entry_type is DeviceEntryType.SERVICE
    assert device.manufacturer == "FORD"
    assert device.model is None
