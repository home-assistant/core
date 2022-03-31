"""Tests for the diagnostics data provided by the RDW integration."""
from aiohttp import ClientSession

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    init_integration: MockConfigEntry,
):
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == {
        "apk_expiration": "2022-01-04",
        "ascription_date": "2021-11-04",
        "ascription_possible": True,
        "brand": "Skoda",
        "energy_label": "A",
        "engine_capacity": 999,
        "exported": False,
        "interior": "hatchback",
        "last_odometer_registration_year": 2021,
        "liability_insured": False,
        "license_plate": "11ZKZ3",
        "list_price": 10697,
        "first_admission": "2013-01-04",
        "mass_empty": 840,
        "mass_driveable": 940,
        "model": "Citigo",
        "number_of_cylinders": 3,
        "number_of_doors": 0,
        "number_of_seats": 4,
        "number_of_wheelchair_seats": 0,
        "number_of_wheels": 4,
        "odometer_judgement": "Logisch",
        "pending_recall": False,
        "taxi": None,
        "vehicle_type": "Personenauto",
    }
