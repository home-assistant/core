"""Tests for the DVLA binary sensor platform."""

from typing import Any
from unittest.mock import patch

from homeassistant.components.dvla.const import CONF_CALENDARS, CONF_REG_NUMBER, DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_SCHEMA: dict[str, Any] = {
    "components": {
        "schemas": {
            "Vehicle": {
                "properties": {
                    "registrationNumber": {
                        "type": "string",
                        "description": "Registration number",
                    },
                    "taxStatus": {
                        "type": "string",
                        "description": "Tax status",
                    },
                    "motStatus": {
                        "type": "string",
                        "description": "Roadworthiness status",
                    },
                    "markedForExport": {
                        "type": "boolean",
                        "description": "Marked for export",
                    },
                    "automatedVehicle": {
                        "type": "boolean",
                        "description": "Automated vehicle",
                    },
                }
            }
        }
    }
}


async def setup_dvla_entry(
    hass: HomeAssistant,
    vehicle_data: dict[str, Any],
) -> None:
    """Set up the DVLA integration with mocked vehicle data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={
            CONF_REG_NUMBER: "AB12CDE",
            CONF_CALENDARS: ["None"],
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.dvla.async_get_schema",
            return_value=MOCK_SCHEMA,
        ),
        patch(
            "homeassistant.components.dvla.coordinator.DVLACoordinator._async_update_data",
            return_value=vehicle_data,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_tax_status_binary_sensor_on(hass: HomeAssistant) -> None:
    """Test taxed status creates an on binary sensor."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "taxStatus": "Taxed",
            "make": "FORD",
        },
    )

    state = hass.states.get("binary_sensor.dvla_ab12cde_taxstatus")

    assert state is not None
    assert state.state == STATE_ON


async def test_tax_status_binary_sensor_off(hass: HomeAssistant) -> None:
    """Test untaxed status creates an off binary sensor."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "taxStatus": "Not Taxed",
            "make": "FORD",
        },
    )

    state = hass.states.get("binary_sensor.dvla_ab12cde_taxstatus")

    assert state is not None
    assert state.state == STATE_OFF


async def test_roadworthiness_binary_sensor_on(hass: HomeAssistant) -> None:
    """Test valid roadworthiness status creates an on binary sensor."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "motStatus": "Valid",
            "make": "FORD",
        },
    )

    state = hass.states.get("binary_sensor.dvla_ab12cde_motstatus")

    assert state is not None
    assert state.state == STATE_ON


async def test_roadworthiness_binary_sensor_off(hass: HomeAssistant) -> None:
    """Test invalid roadworthiness status creates an off binary sensor."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "motStatus": "Invalid",
            "make": "FORD",
        },
    )

    state = hass.states.get("binary_sensor.dvla_ab12cde_motstatus")

    assert state is not None
    assert state.state == STATE_OFF


async def test_boolean_binary_sensors(hass: HomeAssistant) -> None:
    """Test boolean fields are exposed as binary sensors."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "markedForExport": False,
            "automatedVehicle": True,
            "make": "FORD",
        },
    )

    marked_for_export = hass.states.get("binary_sensor.dvla_ab12cde_markedforexport")
    automated_vehicle = hass.states.get("binary_sensor.dvla_ab12cde_automatedvehicle")

    assert marked_for_export is not None
    assert marked_for_export.state == STATE_OFF

    assert automated_vehicle is not None
    assert automated_vehicle.state == STATE_ON


async def test_unknown_string_value_is_off(hass: HomeAssistant) -> None:
    """Test unknown string values fall back to off."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "taxStatus": "SORN",
            "make": "FORD",
        },
    )

    state = hass.states.get("binary_sensor.dvla_ab12cde_taxstatus")

    assert state is not None
    assert state.state == STATE_OFF


async def test_plain_string_fields_are_not_binary_sensors(hass: HomeAssistant) -> None:
    """Test plain string fields without metadata are not binary sensors."""
    await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
        },
    )

    assert hass.states.get("binary_sensor.dvla_ab12cde_registrationnumber") is None
