"""Tests for the DVLA sensor platform."""

from typing import Any
from unittest.mock import patch

from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

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
            "homeassistant.components.dvla.coordinator.DVLACoordinator._async_update_data",
            return_value=vehicle_data or MOCK_VEHICLE_DATA,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_sensor_entities_are_created(hass: HomeAssistant) -> None:
    """Test sensor entities are created from DVLA data."""
    await setup_dvla_entry(hass)

    registration = hass.states.get("sensor.dvla_ab12cde_registrationnumber")
    tax_status = hass.states.get("sensor.dvla_ab12cde_taxstatus")

    assert registration is not None
    assert registration.state == "AB12CDE"

    assert tax_status is not None
    assert tax_status.state == "Taxed"


async def test_date_sensor_values(hass: HomeAssistant) -> None:
    """Test date sensors expose valid date states."""
    await setup_dvla_entry(hass)

    tax_due_date = hass.states.get("sensor.dvla_ab12cde_taxduedate")
    fallback_expiry_date = hass.states.get("sensor.dvla_ab12cde_motexpirydate")

    assert tax_due_date is not None
    assert tax_due_date.state == "2026-03-01"

    assert fallback_expiry_date is not None
    assert fallback_expiry_date.state == "2027-05-01"


async def test_sensor_units(hass: HomeAssistant) -> None:
    """Test sensor units are set from metadata and schema descriptions."""
    await setup_dvla_entry(hass)

    engine_capacity = hass.states.get("sensor.dvla_ab12cde_enginecapacity")
    co2_emissions = hass.states.get("sensor.dvla_ab12cde_co2emissions")

    assert engine_capacity is not None
    assert engine_capacity.state == "1998"
    assert engine_capacity.attributes[ATTR_UNIT_OF_MEASUREMENT] == "cc"

    assert co2_emissions is not None
    assert co2_emissions.state == "150"
    assert co2_emissions.attributes[ATTR_UNIT_OF_MEASUREMENT] == "g/km"


async def test_boolean_fields_are_not_sensor_entities(hass: HomeAssistant) -> None:
    """Test boolean fields are not created as normal sensors."""
    await setup_dvla_entry(hass)

    assert hass.states.get("sensor.dvla_ab12cde_markedforexport") is None


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

    state = hass.states.get("sensor.dvla_ab12cde_revenueweight")

    assert state is not None
    assert state.state == "3500"
    assert state.attributes["unit_of_measurement"] == "kg"
    assert state.attributes["device_class"] == SensorDeviceClass.WEIGHT
