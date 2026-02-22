"""Test the System Bridge integration."""

from unittest.mock import patch

from homeassistant.components.system_bridge.config_flow import SystemBridgeConfigFlow
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.components.system_bridge.services import (
    SERVICE_GET_PROCESS_BY_ID,
    SERVICE_GET_PROCESSES_BY_NAME,
    SERVICE_OPEN_PATH,
    SERVICE_OPEN_URL,
    SERVICE_POWER_COMMAND,
    SERVICE_SEND_KEYPRESS,
    SERVICE_SEND_TEXT,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import FIXTURE_USER_INPUT, FIXTURE_UUID

from tests.common import MockConfigEntry

ALL_SERVICES = (
    SERVICE_GET_PROCESS_BY_ID,
    SERVICE_GET_PROCESSES_BY_NAME,
    SERVICE_OPEN_PATH,
    SERVICE_POWER_COMMAND,
    SERVICE_OPEN_URL,
    SERVICE_SEND_KEYPRESS,
    SERVICE_SEND_TEXT,
)


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

    with patch(
        "homeassistant.components.system_bridge.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1

    # Check that the version has been updated and the api_key has been moved to token
    assert config_entry.version == SystemBridgeConfigFlow.VERSION
    assert config_entry.minor_version == SystemBridgeConfigFlow.MINOR_VERSION
    assert config_entry.data == {
        CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
        CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
        CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
    }
    assert config_entry.state is ConfigEntryState.LOADED


async def test_migration_minor_future_version(hass: HomeAssistant) -> None:
    """Test migration."""
    config_entry_data = {
        CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
        CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
        CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
    }
    config_entry_version = SystemBridgeConfigFlow.VERSION
    config_entry_minor_version = SystemBridgeConfigFlow.MINOR_VERSION + 1
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data=config_entry_data,
        version=config_entry_version,
        minor_version=config_entry_minor_version,
    )

    with patch(
        "homeassistant.components.system_bridge.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1

    assert config_entry.version == config_entry_version
    assert config_entry.minor_version == config_entry_minor_version
    assert config_entry.data == config_entry_data
    assert config_entry.state is ConfigEntryState.LOADED


async def test_setup_timeout(hass: HomeAssistant) -> None:
    """Test setup with timeout error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data=FIXTURE_USER_INPUT,
        version=SystemBridgeConfigFlow.VERSION,
        minor_version=SystemBridgeConfigFlow.MINOR_VERSION,
    )

    with patch(
        "systembridgeconnector.version.Version.check_supported",
        side_effect=TimeoutError,
    ):
        config_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is False
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_get_data_timeout(hass: HomeAssistant) -> None:
    """Test coordinator handling timeout during get_data."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data=FIXTURE_USER_INPUT,
        version=SystemBridgeConfigFlow.VERSION,
        minor_version=SystemBridgeConfigFlow.MINOR_VERSION,
    )

    with (
        patch(
            "systembridgeconnector.version.Version.check_supported",
            return_value=True,
        ),
        patch(
            "homeassistant.components.system_bridge.coordinator.SystemBridgeDataUpdateCoordinator.async_get_data",
            side_effect=TimeoutError,
        ),
    ):
        config_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is False
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_last_entry_removes_services(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test unloading the last entry removes all registered services."""
    for service in ALL_SERVICES:
        assert hass.services.has_service(DOMAIN, service)

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    for service in ALL_SERVICES:
        assert not hass.services.has_service(DOMAIN, service)
