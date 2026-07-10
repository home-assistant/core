"""Tests for the DVLA integration setup."""

from unittest.mock import patch

from homeassistant.components.dvla.const import (
    ATTR_REG_NUMBER,
    CONF_CALENDARS,
    CONF_REG_NUMBER,
    DOMAIN,
    SERVICE_LOOKUP,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_SCHEMA = {
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
                        "description": "M.O.T status",
                    },
                }
            }
        }
    }
}


async def test_async_setup_registers_lookup_service(hass: HomeAssistant) -> None:
    """Test setup registers the lookup service."""
    assert not hass.services.has_service(DOMAIN, SERVICE_LOOKUP)

    assert await async_setup_component(hass, DOMAIN, {})

    assert hass.services.has_service(DOMAIN, SERVICE_LOOKUP)


async def test_lookup_service_returns_response(hass: HomeAssistant) -> None:
    """Test lookup service returns a DVLA response."""
    assert await async_setup_component(hass, DOMAIN, {})

    with patch(
        "homeassistant.components.dvla._async_single_lookup",
        return_value={
            "registrationNumber": "AB12CDE",
            "make": "FORD",
            "taxStatus": "Taxed",
        },
    ) as mock_lookup:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_LOOKUP,
            {ATTR_REG_NUMBER: "AB12CDE"},
            blocking=True,
            return_response=True,
        )

    assert response == {
        "registrationNumber": "AB12CDE",
        "make": "FORD",
        "taxStatus": "Taxed",
    }
    mock_lookup.assert_called_once_with(hass, "AB12CDE")


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up a config entry."""
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
    assert entry.runtime_data["schema"] == MOCK_SCHEMA
    assert entry.runtime_data["coordinator"] is not None
    mock_forward_entry_setups.assert_called_once()


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading a config entry."""
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
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=True,
    ) as mock_unload_platforms:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_unload_platforms.assert_called_once()
