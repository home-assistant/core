"""Test the DVLA integration setup."""

from unittest.mock import patch

from aio_dvla_vehicle_enquiry import DVLAError

from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

VEHICLE_DATA = {
    "registrationNumber": "AB12CDE",
    "make": "FORD",
    "taxStatus": "Taxed",
}


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test the component setup."""
    assert await async_setup_component(hass, DOMAIN, {})


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={CONF_REG_NUMBER: "AB12CDE"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.dvla.coordinator.DVLACoordinator._async_update_data",
            return_value={
                "registrationNumber": "AB12CDE",
                "make": "FORD",
                "taxStatus": "Taxed",
            },
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            return_value=True,
        ) as mock_forward_entry_setups,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data["coordinator"] is not None
    mock_forward_entry_setups.assert_awaited_once()


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={CONF_REG_NUMBER: "AB12CDE"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
        return_value=VEHICLE_DATA,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    entity_registry = er.async_get(hass)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry,
        entry.entry_id,
    )
    assert entity_entries

    entity_ids = {entity_entry.entity_id for entity_entry in entity_entries}
    assert all(hass.states.get(entity_id) is not None for entity_id in entity_ids)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "unavailable"
        assert state.attributes["restored"] is True


async def test_setup_entry_first_refresh_failure(hass: HomeAssistant) -> None:
    """Test config entry setup retries when the first refresh fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={CONF_REG_NUMBER: "AB12CDE"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
        side_effect=DVLAError("DVLA unavailable"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
