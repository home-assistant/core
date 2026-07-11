"""Tests for the DVLA sensor platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

MOCK_VEHICLE_DATA: dict[str, Any] = {
    "registrationNumber": "AB12CDE",
    "taxStatus": "Taxed",
    "taxDueDate": "2026-03-01",
    "engineCapacity": 1998,
    "co2Emissions": 150,
    "monthOfFirstRegistration": "2024-05",
    "markedForExport": False,
    "make": "FORD",
}


def get_entity_id(hass: HomeAssistant, key: str) -> str:
    """Get entity ID by DVLA sensor key."""
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"ab12cde-{key}".lower(),
    )

    assert entity_id is not None

    return entity_id


def get_state(hass: HomeAssistant, key: str) -> State:
    """Get DVLA sensor state by sensor key."""
    return hass.states.get(get_entity_id(hass, key))


async def setup_dvla_entry(
    hass: HomeAssistant,
    vehicle_data: dict[str, Any] | None = None,
) -> None:
    """Set up the DVLA integration with mocked vehicle data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={
            CONF_REG_NUMBER: "AB12CDE",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
            return_value=vehicle_data
            if vehicle_data is not None
            else MOCK_VEHICLE_DATA,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_sensor_entities_are_created(hass: HomeAssistant) -> None:
    """Test sensor entities are created from DVLA data."""
    await setup_dvla_entry(hass)

    registration = get_state(hass, "registrationNumber")
    tax_status = get_state(hass, "taxStatus")

    assert registration.state == "AB12CDE"
    assert tax_status.state == "Taxed"


async def test_date_sensor_values_and_missing_mot_expiry(
    hass: HomeAssistant,
) -> None:
    """Test date sensors expose valid date states."""
    await setup_dvla_entry(hass)

    tax_due_date = get_state(hass, "taxDueDate")
    expiry_date = get_state(hass, "motExpiryDate")

    assert tax_due_date.state == "2026-03-01"
    assert expiry_date.state == "unknown"


async def test_sensor_units(hass: HomeAssistant) -> None:
    """Test sensor units are set from metadata and schema descriptions."""
    await setup_dvla_entry(hass)

    engine_capacity = get_state(hass, "engineCapacity")
    co2_emissions = get_state(hass, "co2Emissions")

    assert engine_capacity.attributes["unit_of_measurement"] == "cc"
    assert co2_emissions.attributes["unit_of_measurement"] == "g/km"


async def test_boolean_fields_are_not_sensor_entities(hass: HomeAssistant) -> None:
    """Test boolean fields are not created as normal sensors."""
    await setup_dvla_entry(hass)

    entity_registry = er.async_get(hass)

    assert (
        entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            "ab12cde-markedforexport",
        )
        is None
    )


async def test_revenue_weight_sensor_is_numeric(hass: HomeAssistant) -> None:
    """Test revenue weight is exposed as a numeric weight sensor."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "revenueWeight": "3500",
        },
    )

    state = get_state(hass, "revenueWeight")

    assert state.state == "3500"
    assert state.attributes["unit_of_measurement"] == "kg"
    assert state.attributes["device_class"] == SensorDeviceClass.WEIGHT


async def test_revenue_weight_sensor_is_unknown_for_invalid_value(
    hass: HomeAssistant,
) -> None:
    """Test revenue weight is unknown when DVLA returns a non-numeric value."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "revenueWeight": "not-a-number",
        },
    )

    state = get_state(hass, "revenueWeight")

    assert state is not None
    assert state.state == "unknown"


async def test_month_of_first_registration_is_string_sensor(
    hass: HomeAssistant,
) -> None:
    """Test month-only registration value is exposed as a string sensor."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "monthOfFirstRegistration": "2024-05",
        },
    )

    state = get_state(hass, "monthOfFirstRegistration")

    assert state is not None
    assert state.state == "2024-05"


async def test_sensor_updates_after_scheduled_refresh(hass: HomeAssistant) -> None:
    """Test sensor updates after a scheduled refresh."""
    updated_vehicle_data = {
        **MOCK_VEHICLE_DATA,
        "registrationNumber": "XY99ZZZ",
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

        state = get_state(hass, "registrationNumber")
        assert state.state == "AB12CDE"

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1, seconds=1))
        await hass.async_block_till_done()

    state = get_state(hass, "registrationNumber")
    assert state.state == "XY99ZZZ"


async def test_invalid_date_sensor_value_is_unknown(hass: HomeAssistant) -> None:
    """Test invalid date sensor values are exposed as unknown."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "taxDueDate": "not-a-date",
        },
    )

    state = get_state(hass, "taxDueDate")

    assert state is not None
    assert state.state == "unknown"


async def test_registration_month_fields_are_distinct(
    hass: HomeAssistant,
) -> None:
    """Test first registration month fields are not substituted."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "monthOfFirstDvlaRegistration": "2024-05",
        },
    )

    first_registration = get_state(hass, "monthOfFirstRegistration")
    first_dvla_registration = get_state(hass, "monthOfFirstDvlaRegistration")

    assert first_registration.state == "unknown"
    assert first_dvla_registration.state == "2024-05"


async def test_mot_expiry_date_sensor_value(hass: HomeAssistant) -> None:
    """Test MOT expiry date is exposed when returned by DVLA."""  # codespell:ignore

    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "motExpiryDate": "2026-11-30",
        },
    )

    state = get_state(hass, "motExpiryDate")

    assert state.state == "2026-11-30"


async def test_device_entry_type(hass: HomeAssistant) -> None:
    """Test DVLA device is marked as a service."""
    await setup_dvla_entry(hass)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, "AB12CDE")})

    assert device is not None
    assert device.entry_type is DeviceEntryType.SERVICE
    assert device.manufacturer == "FORD"
    assert device.model is None
    assert device.entry_type is DeviceEntryType.SERVICE
