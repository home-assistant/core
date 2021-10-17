"""Provide common Renault fixtures."""
import pytest

from homeassistant.components.renault.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG, MOCK_VEHICLES

from tests.common import MockConfigEntry


@pytest.fixture(name="vehicle_type", params=MOCK_VEHICLES.keys())
def get_vehicle_type(request):
    """Parametrize vehicle type."""
    return request.param


@pytest.fixture(name="config_entry")
def get_config_entry(hass: HomeAssistant):
    """Create and register mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=MOCK_CONFIG,
        unique_id="account_id_1",
        options={},
        entry_id="123456",
    )
    config_entry.add_to_hass(hass)
    return config_entry
