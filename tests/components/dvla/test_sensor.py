"""Tests for the DVLA sensor platform."""

from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.components.dvla.coordinator import DVLACoordinator
from homeassistant.components.dvla.sensor import DVLASensor
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
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


async def test_date_sensor_values_and_missing_mot_expiry(hass: HomeAssistant) -> None:
    """Test date sensors expose valid date states."""
    await setup_dvla_entry(hass)

    tax_due_date = hass.states.get("sensor.dvla_ab12cde_taxduedate")
    mot_expiry_date = hass.states.get("sensor.dvla_ab12cde_motexpirydate")

    assert tax_due_date is not None
    assert tax_due_date.state == "2026-03-01"

    assert mot_expiry_date is not None
    assert mot_expiry_date.state == "unknown"


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

    state = hass.states.get("sensor.dvla_ab12cde_revenueweight")

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

    state = hass.states.get("sensor.dvla_ab12cde_monthoffirstregistration")

    assert state is not None
    assert state.state == "2024-05"


async def test_sensor_handle_coordinator_update(hass: HomeAssistant) -> None:
    """Test sensor handles coordinator updates."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={CONF_REG_NUMBER: "AB12CDE"},
    )
    entry.add_to_hass(hass)

    coordinator = DVLACoordinator(
        hass,
        entry,
        MagicMock(),
        "AB12CDE",
    )
    coordinator.data = {"registrationNumber": "AB12CDE"}

    sensor = DVLASensor(
        coordinator,
        "AB12CDE",
        SensorEntityDescription(
            key="registrationNumber",
            name="Registration number",
        ),
    )

    assert sensor.native_value == "AB12CDE"

    coordinator.data = {"registrationNumber": "XY99ZZZ"}

    with patch.object(sensor, "async_write_ha_state") as mock_write_state:
        sensor._handle_coordinator_update()

    assert sensor.native_value == "XY99ZZZ"
    mock_write_state.assert_called_once()


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

    state = hass.states.get("sensor.dvla_ab12cde_taxduedate")

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

    first_registration = hass.states.get("sensor.dvla_ab12cde_monthoffirstregistration")
    first_dvla_registration = hass.states.get(
        "sensor.dvla_ab12cde_monthoffirstdvlaregistration"
    )

    assert first_registration is not None
    assert first_registration.state == "unknown"

    assert first_dvla_registration is not None
    assert first_dvla_registration.state == "2024-05"


async def test_mot_expiry_date_sensor_value(hass: HomeAssistant) -> None:
    """Test M.O.T expiry date is exposed when returned by DVLA."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "motExpiryDate": "2026-11-30",
        },
    )

    state = hass.states.get("sensor.dvla_ab12cde_motexpirydate")

    assert state is not None
    assert state.state == "2026-11-30"
