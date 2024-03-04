"""Test the System Bridge integration."""

from homeassistant.components.system_bridge.config_flow import SystemBridgeConfigFlow
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import FIXTURE_USER_INPUT, FIXTURE_UUID

from tests.common import MockConfigEntry


async def test_migration_minor_1_to_2(hass: HomeAssistant) -> None:
    """Test migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data={
            CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
            CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
            CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        },
        version=SystemBridgeConfigFlow.VERSION,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that the version has been updated and the api_key has been moved to token
    assert config_entry.version == SystemBridgeConfigFlow.VERSION
    assert config_entry.minor_version == SystemBridgeConfigFlow.MINOR_VERSION
    assert config_entry.data[CONF_TOKEN] == FIXTURE_USER_INPUT[CONF_TOKEN]
    assert config_entry.data == {
        CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
        CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
        CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
    }
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_migration_minor_future_to_2(hass: HomeAssistant) -> None:
    """Test migration."""
    config_entry_data = {
        CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
        CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
        CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data=config_entry_data,
        version=SystemBridgeConfigFlow.VERSION,
        minor_version=SystemBridgeConfigFlow.MINOR_VERSION + 1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that the version has been updated
    assert config_entry.version == SystemBridgeConfigFlow.VERSION
    assert config_entry.minor_version == SystemBridgeConfigFlow.MINOR_VERSION
    assert config_entry.data[CONF_API_KEY] == FIXTURE_USER_INPUT[CONF_TOKEN]
    assert config_entry.data == config_entry_data
    assert config_entry.state == ConfigEntryState.SETUP_RETRY
