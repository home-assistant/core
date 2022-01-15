"""Test cases for the initialisation of the Huisbaasje integration."""
from unittest.mock import patch

from huisbaasje import HuisbaasjeException

from homeassistant.components import huisbaasje
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.huisbaasje.test_data import MOCK_CURRENT_MEASUREMENTS


async def test_setup(hass: HomeAssistant):
    """Test for successfully setting up the platform."""
    assert await async_setup_component(hass, huisbaasje.DOMAIN, {})
    await hass.async_block_till_done()
    assert huisbaasje.DOMAIN in hass.config.components


async def test_setup_entry(hass: HomeAssistant):
    """Test for successfully setting a config entry."""
    with patch(
        "huisbaasje.Huisbaasje.authenticate", return_value=None
    ) as mock_authenticate, patch(
        "huisbaasje.Huisbaasje.is_authenticated", return_value=True
    ) as mock_is_authenticated, patch(
        "huisbaasje.Huisbaasje.current_measurements",
        return_value=MOCK_CURRENT_MEASUREMENTS,
    ) as mock_current_measurements:
        hass.config.components.add(huisbaasje.DOMAIN)
        config_entry = MockConfigEntry(
            version=1,
            domain=huisbaasje.DOMAIN,
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
        assert huisbaasje.DOMAIN in hass.config.components
        assert huisbaasje.DOMAIN in hass.data
        assert config_entry.entry_id in hass.data[huisbaasje.DOMAIN]

        # Assert entities are loaded
        entities = hass.states.async_entity_ids("sensor")
        assert len(entities) == 18

        # Assert mocks are called
        assert len(mock_authenticate.mock_calls) == 1
        assert len(mock_is_authenticated.mock_calls) == 1
        assert len(mock_current_measurements.mock_calls) == 1


async def test_setup_entry_error(hass: HomeAssistant):
    """Test for successfully setting a config entry."""
    with patch(
        "huisbaasje.Huisbaasje.authenticate", side_effect=HuisbaasjeException
    ) as mock_authenticate:
        hass.config.components.add(huisbaasje.DOMAIN)
        config_entry = MockConfigEntry(
            version=1,
            domain=huisbaasje.DOMAIN,
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
        assert huisbaasje.DOMAIN not in hass.data

        # Assert entities are not loaded
        entities = hass.states.async_entity_ids("sensor")
        assert len(entities) == 0

        # Assert mocks are called
        assert len(mock_authenticate.mock_calls) == 1


async def test_unload_entry(hass: HomeAssistant):
    """Test for successfully unloading the config entry."""
    with patch(
        "huisbaasje.Huisbaasje.authenticate", return_value=None
    ) as mock_authenticate, patch(
        "huisbaasje.Huisbaasje.is_authenticated", return_value=True
    ) as mock_is_authenticated, patch(
        "huisbaasje.Huisbaasje.current_measurements",
        return_value=MOCK_CURRENT_MEASUREMENTS,
    ) as mock_current_measurements:
        hass.config.components.add(huisbaasje.DOMAIN)
        config_entry = MockConfigEntry(
            version=1,
            domain=huisbaasje.DOMAIN,
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
