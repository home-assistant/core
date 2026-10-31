"""Tests for the DVLA sensor platform."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import STATE_UNKNOWN
from homeassistant.util import dt as dt_util

from tests.common import (
    AsyncMock,
    MockConfigEntry,
    SnapshotAssertion,
    async_fire_time_changed,
    snapshot_platform,
)

MOCK_VEHICLE_DATA: dict[str, Any] = {
    "registrationNumber": "AB12CDE",
    "taxStatus": "Taxed",
    "taxDueDate": "2026-03-01",
    "engineCapacity": 1998,
    "co2Emissions": 150,
    "monthOfFirstRegistration": "2024-05",
    "markedForExport": False,
    "make": "FORD",
    "yearOfManufacture": 2020,
}


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


async def test_unknown_enum_sensor_value_is_unknown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
) -> None:
    """Test unknown enum sensor values are exposed as unknown."""
    await setup_dvla_entry(
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "taxStatus": "Unexpected",
        },
    )

    state = get_state(hass, entity_registry, "taxStatus")

    assert state.state == STATE_UNKNOWN


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


async def test_boolean_fields_are_not_sensor_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
) -> None:
    """Test boolean fields are not created as normal sensors."""
    await setup_dvla_entry()

    assert (
        entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            "AB12CDE-markedForExport",
        )
        is None
    )


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


async def test_revenue_weight_sensor_is_unknown_for_invalid_value(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
) -> None:
    """Test revenue weight is unknown when DVLA returns a non-numeric value."""
    await setup_dvla_entry(
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "revenueWeight": "not-a-number",
        },
    )

    state = get_state(hass, entity_registry, "revenueWeight")

    assert state is not None
    assert state.state == "unknown"


async def test_sensor_updates_after_scheduled_refresh(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test sensor updates after a scheduled refresh."""
    updated_vehicle_data = {
        **MOCK_VEHICLE_DATA,
        "taxStatus": "Untaxed",
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={CONF_REG_NUMBER: "AB12CDE"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
        side_effect=[MOCK_VEHICLE_DATA, updated_vehicle_data],
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = get_state(hass, entity_registry, "taxStatus")
        assert state.state == "taxed"

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1, seconds=1))
        await hass.async_block_till_done()

    state = get_state(hass, entity_registry, "taxStatus")
    assert state.state == "untaxed"


async def test_invalid_date_sensor_value_is_unknown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
) -> None:
    """Test invalid date sensor values are exposed as unknown."""
    await setup_dvla_entry(
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "taxDueDate": "not-a-date",
        },
    )

    state = get_state(hass, entity_registry, "taxDueDate")

    assert state is not None
    assert state.state == "unknown"


async def test_month_of_first_registration_is_not_substituted(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
) -> None:
    """Test first registration month is not substituted from DVLA registration month."""
    await setup_dvla_entry(
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "monthOfFirstDvlaRegistration": "2024-05",
        },
    )

    first_registration = get_state(hass, entity_registry, "monthOfFirstRegistration")

    assert first_registration.state == STATE_UNKNOWN
    assert (
        entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            "AB12CDE-monthOfFirstDvlaRegistration",
        )
        is None
    )


async def test_missing_mot_expiry_date_is_unknown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
) -> None:
    """Test MOT expiry date is unknown when omitted by DVLA."""  # codespell:ignore

    await setup_dvla_entry(
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
        },
    )

    state = get_state(hass, entity_registry, "motExpiryDate")

    assert state.state == STATE_UNKNOWN


async def test_device_entry_type(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
) -> None:
    """Test DVLA device is marked as a service."""
    await setup_dvla_entry()

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "AB12CDE"),
        entry.entry_id,
    )

    assert device is not None
    assert device.entry_type is DeviceEntryType.SERVICE
    assert device.manufacturer == "FORD"
    assert device.model is None


async def test_date_sensor_non_string_value_is_unknown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
) -> None:
    """Test non-string date sensor values are exposed as unknown."""
    await setup_dvla_entry(
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "taxDueDate": 123,
        },
    )

    state = get_state(hass, entity_registry, "taxDueDate")

    assert state.state == STATE_UNKNOWN


async def test_setup_entry_fetches_vehicle_data(
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
    mock_dvla_client: AsyncMock,
) -> None:
    """Test setup fetches vehicle data through the coordinator."""
    entry = await setup_dvla_entry()

    assert entry.state is ConfigEntryState.LOADED
    mock_dvla_client.assert_awaited_once_with("AB12CDE")
