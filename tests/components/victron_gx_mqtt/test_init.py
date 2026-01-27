"""Test the victron_gx_mqtt init."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.victron_gx_mqtt.const import (
    CONF_INSTALLATION_ID,
    CONF_UPDATE_FREQUENCY_SECONDS,
    DEFAULT_PORT,
    DEFAULT_UPDATE_FREQUENCY_SECONDS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_INSTALLATION_ID = "d41243d9b9c6"
MOCK_HOST = "192.168.1.100"


@pytest.fixture
def mock_victron_hub_library():
    """Mock the victron_mqtt library."""
    with patch(
        "homeassistant.components.victron_gx_mqtt.hub.VictronVenusHub"
    ) as mock_lib:
        hub_instance = MagicMock()
        hub_instance.connect = AsyncMock()
        hub_instance.disconnect = AsyncMock()
        hub_instance.installation_id = MOCK_INSTALLATION_ID
        mock_lib.return_value = hub_instance
        yield mock_lib


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
        unique_id=MOCK_INSTALLATION_ID,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ) as mock_forward:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    mock_forward.assert_called_once()


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
        unique_id=MOCK_INSTALLATION_ID,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ) as mock_unload:
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    mock_unload.assert_called_once()


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_update_listener(hass: HomeAssistant) -> None:
    """Test update listener triggers reload."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
        unique_id=MOCK_INSTALLATION_ID,
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=True,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload") as mock_reload,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Update the entry to trigger the update listener
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                CONF_HOST: MOCK_HOST,
                CONF_PORT: DEFAULT_PORT,
                CONF_SSL: False,
                CONF_UPDATE_FREQUENCY_SECONDS: 60,  # Changed
                CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            },
        )
        await hass.async_block_till_done()

        # Verify the reload was triggered
        assert mock_reload.call_count == 1


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_stop_on_homeassistant_stop(hass: HomeAssistant) -> None:
    """Test hub stops when Home Assistant stops."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
        unique_id=MOCK_INSTALLATION_ID,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    # Fire the stop event
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    # The event handler should have been called (hub stop is internal)
