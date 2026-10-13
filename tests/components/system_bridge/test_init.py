"""Test the System Bridge integration."""

from unittest.mock import MagicMock, patch

import pytest
from systembridgeconnector.exceptions import (
    ConnectionErrorException,
    DataMissingException,
)
from systembridgeconnector.models.modules import ModulesData

from homeassistant.components.system_bridge.config_flow import SystemBridgeConfigFlow
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import FIXTURE_USER_INPUT, FIXTURE_UUID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_version")
async def test_entry_setup_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test integration setup and unload."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_websocket_client.close.assert_not_awaited()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_websocket_client.close.assert_awaited_once()


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


@pytest.mark.usefixtures("mock_version", "mock_websocket_client")
async def test_migration_minor_2_to_3(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration of entity unique ids."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data={
            CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
            CONF_HOST: "hostname",
            CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        },
        version=1,
        minor_version=2,
    )

    config_entry.add_to_hass(hass)
    assert config_entry.minor_version == 2

    sensor = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="hostname_cpu_speed",
        config_entry=config_entry,
        original_name="hostname CPU speed",
    )

    notifier = entity_registry.async_get_or_create(
        domain="notify",
        platform=DOMAIN,
        unique_id="hostname",
        config_entry=config_entry,
        original_name="hostname",
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 1
    assert config_entry.minor_version == 3

    assert (
        entity_registry.async_get(sensor.entity_id).unique_id
        == f"{FIXTURE_UUID}_cpu_speed"
    )

    assert entity_registry.async_get(notifier.entity_id).unique_id == FIXTURE_UUID

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


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        pytest.param(TimeoutError, None, id="timeout"),
        pytest.param(ConnectionErrorException, None, id="connection_error"),
        pytest.param(DataMissingException, None, id="data_missing"),
        pytest.param(None, ModulesData(), id="missing_system"),
    ],
)
@pytest.mark.usefixtures("mock_version")
async def test_get_data_failure_closes_websocket(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
    side_effect: type[Exception] | None,
    return_value: ModulesData | None,
) -> None:
    """Test setup retries and closes the websocket when getting data fails."""
    mock_websocket_client.get_data.side_effect = side_effect
    mock_websocket_client.get_data.return_value = return_value

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_websocket_client.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_version")
async def test_platform_setup_failure_cleans_up(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test the stop listener is removed when setup fails after the first refresh."""
    assert await async_setup_component(hass, "media_source", {})
    stop_listeners = hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_STOP, 0)

    mock_config_entry.add_to_hass(hass)
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=ConfigEntryNotReady,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_STOP, 0) == stop_listeners
    mock_websocket_client.close.assert_awaited_once()
