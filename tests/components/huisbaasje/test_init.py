"""Test cases for the initialisation of the Huisbaasje integration."""

from unittest.mock import patch

from energyflip import EnergyFlipException

from homeassistant.components.huisbaasje.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .test_data import MOCK_CURRENT_MEASUREMENTS

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test for successfully setting a config entry."""
    with (
        patch(
            "energyflip.EnergyFlip.authenticate", return_value=None
        ) as mock_authenticate,
        patch(
            "energyflip.EnergyFlip.is_authenticated", return_value=True
        ) as mock_is_authenticated,
        patch(
            "energyflip.EnergyFlip.current_measurements",
            return_value=MOCK_CURRENT_MEASUREMENTS,
        ) as mock_current_measurements,
    ):
        config_entry = MockConfigEntry(
            version=1,
            domain=DOMAIN,
            title="userId",
            data={
                CONF_ID: "userId",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
            source="test",
        )
        config_entry.add_to_hass(hass)

        assert config_entry.state is ConfigEntryState.NOT_LOADED
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Assert integration is loaded
        assert config_entry.state is ConfigEntryState.LOADED

        # Assert entities are loaded
        entities = hass.states.async_entity_ids("sensor")
        assert len(entities) == 18

        # Assert mocks are called
        assert len(mock_authenticate.mock_calls) == 1
        assert len(mock_is_authenticated.mock_calls) == 1
        assert len(mock_current_measurements.mock_calls) == 1


async def test_setup_entry_error(hass: HomeAssistant) -> None:
    """Test for successfully setting a config entry."""
    with patch(
        "energyflip.EnergyFlip.authenticate", side_effect=EnergyFlipException
    ) as mock_authenticate:
        config_entry = MockConfigEntry(
            version=1,
            domain=DOMAIN,
            title="userId",
            data={
                CONF_ID: "userId",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
            source="test",
        )
        config_entry.add_to_hass(hass)

        assert config_entry.state is ConfigEntryState.NOT_LOADED
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Assert integration is loaded with error
        assert config_entry.state is ConfigEntryState.SETUP_ERROR
        assert DOMAIN not in hass.data

        # Assert entities are not loaded
        entities = hass.states.async_entity_ids("sensor")
        assert len(entities) == 0

        # Assert mocks are called
        assert len(mock_authenticate.mock_calls) == 1


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test for successfully unloading the config entry."""
    with (
        patch(
            "energyflip.EnergyFlip.authenticate", return_value=None
        ) as mock_authenticate,
        patch(
            "energyflip.EnergyFlip.is_authenticated", return_value=True
        ) as mock_is_authenticated,
        patch(
            "energyflip.EnergyFlip.current_measurements",
            return_value=MOCK_CURRENT_MEASUREMENTS,
        ) as mock_current_measurements,
    ):
        config_entry = MockConfigEntry(
            version=1,
            domain=DOMAIN,
            title="userId",
            data={
                CONF_ID: "userId",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
            source="test",
        )
        config_entry.add_to_hass(hass)

        # Load config entry
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
        entities = hass.states.async_entity_ids("sensor")
        assert len(entities) == 18

        # Unload config entry
        await hass.config_entries.async_unload(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.NOT_LOADED
        entities = hass.states.async_entity_ids("sensor")
        assert len(entities) == 18
        for entity in entities:
            assert hass.states.get(entity).state == STATE_UNAVAILABLE

        # Remove config entry
        await hass.config_entries.async_remove(config_entry.entry_id)
        await hass.async_block_till_done()
        entities = hass.states.async_entity_ids("sensor")
        assert len(entities) == 0

        # Assert mocks are called
        assert len(mock_authenticate.mock_calls) == 1
        assert len(mock_is_authenticated.mock_calls) == 1
        assert len(mock_current_measurements.mock_calls) == 1
