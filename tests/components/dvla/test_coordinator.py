"""Tests for the DVLA data update coordinator through config entry setup."""

from unittest.mock import patch

from aio_dvla_vehicle_enquiry import DVLAError

from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

VEHICLE_DATA = {
    "registrationNumber": "AB12CDE",
    "make": "FORD",
    "taxStatus": "Taxed",
}


async def test_setup_entry_fetches_vehicle_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup fetches vehicle data through the coordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={CONF_REG_NUMBER: "AB12CDE"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
        return_value=VEHICLE_DATA,
    ) as mock_get_vehicle:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_get_vehicle.assert_awaited_once_with("AB12CDE")

    entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        "AB12CDE-taxStatus",
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "taxed"


async def test_setup_entry_normalizes_registration_number(
    hass: HomeAssistant,
) -> None:
    """Test setup normalizes the registration number before fetching data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={CONF_REG_NUMBER: "ab12 cde"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
        return_value=VEHICLE_DATA,
    ) as mock_get_vehicle:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_get_vehicle.assert_awaited_once_with("AB12CDE")


async def test_setup_entry_retries_on_dvla_error(hass: HomeAssistant) -> None:
    """Test setup retries when the DVLA client raises an error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={CONF_REG_NUMBER: "AB12CDE"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
        side_effect=DVLAError("Vehicle not found"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
