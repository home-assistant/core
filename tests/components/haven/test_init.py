"""Test setup for the HAVEN IAQ integration."""

from dataclasses import replace
from ipaddress import ip_address
from unittest.mock import AsyncMock

from haveniaq import (
    DeviceInfo,
    HavenApiError,
    HavenUnsupportedApiVersionError,
    HavenUnsupportedProductError,
)
import pytest

from homeassistant.components.haven.const import DOMAIN
from homeassistant.config_entries import SOURCE_ZEROCONF, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from . import TEST_HOST, TEST_INFO, TEST_SERIAL, ZEROCONF_DISCOVERY, setup_integration

from tests.common import MockConfigEntry


async def test_setup_unload_ram_entry(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up and unloading an air-quality entry."""
    await setup_integration(hass, mock_config_entry)

    mock_haven_client.get_info.assert_awaited_once()
    mock_haven_client.get_sensors.assert_awaited_once()
    mock_haven_client.get_status.assert_not_awaited()
    mock_haven_client.get_controller.assert_not_awaited()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        pytest.param(
            HavenUnsupportedApiVersionError("Unsupported API version"),
            ConfigEntryState.SETUP_ERROR,
            id="unsupported-api-version",
        ),
        pytest.param(
            HavenUnsupportedProductError("Unsupported product"),
            ConfigEntryState.SETUP_ERROR,
            id="unsupported-product",
        ),
        pytest.param(
            HavenApiError("Unable to connect"),
            ConfigEntryState.SETUP_RETRY,
            id="cannot-connect",
        ),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup retries only for transient errors."""
    mock_haven_client.get_info.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
    mock_haven_client.get_sensors.assert_not_awaited()


async def test_setup_wrong_device_then_rediscovery(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an IP reassignment cannot load another device into the entry."""
    mock_haven_client.get_info.return_value = DeviceInfo.from_dict(
        {**TEST_INFO, "serial_number": "OTHER-RAM-0002"}
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.unique_id == TEST_SERIAL
    assert mock_config_entry.data == {CONF_HOST: TEST_HOST}
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    mock_haven_client.get_sensors.assert_not_awaited()

    mock_haven_client.get_info.return_value = DeviceInfo.from_dict(TEST_INFO)
    new_host = "192.0.2.2"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=replace(
            ZEROCONF_DISCOVERY,
            ip_address=ip_address(new_host),
            ip_addresses=[ip_address(new_host)],
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_HOST: new_host}
    assert mock_config_entry.unique_id == TEST_SERIAL
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{TEST_SERIAL}_temperature_c"
        )
        is not None
    )
    mock_haven_client.get_sensors.assert_awaited_once()
