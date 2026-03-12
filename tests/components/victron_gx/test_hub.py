"""Test the Victron GX MQTT Hub class."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from victron_mqtt import (
    AuthenticationError,
    Device as VictronVenusDevice,
    Hub as VictronVenusHub,
)
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.victron_gx.const import (
    CONF_INSTALLATION_ID,
    CONF_MODEL,
    CONF_ROOT_TOPIC_PREFIX,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.components.victron_gx.hub import Hub
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def basic_config():
    """Provide basic configuration."""
    return {
        CONF_HOST: "venus.local",
        CONF_PORT: 1883,
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
        CONF_SSL: False,
        CONF_INSTALLATION_ID: "123",
        CONF_MODEL: "Venus GX",
        CONF_SERIAL: "HQ12345678",
        CONF_ROOT_TOPIC_PREFIX: "N/",
    }


@pytest.fixture
def mock_config_entry(basic_config):
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_unique_id",
        data=basic_config,
    )


@pytest.fixture
def mock_victron_hub():
    """Create a mock VictronVenusHub."""
    with patch(
        "homeassistant.components.victron_gx.hub.VictronVenusHub"
    ) as mock_hub_class:
        mock_hub = MagicMock(spec=VictronVenusHub)
        mock_hub.connect = AsyncMock()
        mock_hub.disconnect = AsyncMock()
        mock_hub.publish = MagicMock()
        mock_hub.installation_id = "123"
        mock_hub_class.return_value = mock_hub
        yield mock_hub


async def test_hub_start_success(hass: HomeAssistant, init_integration) -> None:
    """Test successful hub start."""
    victron_hub, mock_config_entry = init_integration

    # Verify the hub was started (integration was set up successfully)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert victron_hub.installation_id == "123"


async def test_hub_start_authentication_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test hub start with authentication error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victron_gx.hub.VictronVenusHub.connect",
        side_effect=AuthenticationError("Authentication failed"),
    ):
        # Attempt to set up the config entry - should fail with auth error
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify the config entry is in SETUP_ERROR state (auth failed)
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_hub_stop(hass: HomeAssistant, init_integration) -> None:
    """Test hub stop."""
    _, mock_config_entry = init_integration

    # Verify it's initially loaded
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Unload the config entry (which stops the hub)
    unload_ok = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify hub is disconnected by checking config entry state
    assert unload_ok is True
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_map_device_info() -> None:
    """Test _map_device_info static method."""
    mock_device = MagicMock(spec=VictronVenusDevice)
    mock_device.unique_id = "device_123"
    mock_device.manufacturer = "Victron Energy"
    mock_device.name = "Battery Monitor"
    mock_device.device_id = "288"
    mock_device.model = "BMV-712"
    mock_device.serial_number = "HQ12345678"

    installation_id = "12345"

    device_info = Hub._map_device_info(mock_device, installation_id)

    assert device_info.get("identifiers") == {(DOMAIN, "12345_device_123")}
    assert device_info.get("manufacturer") == "Victron Energy"
    assert device_info.get("name") == "Battery Monitor (ID: 288)"
    assert device_info.get("model") == "BMV-712"
    assert device_info.get("serial_number") == "HQ12345678"


async def test_map_device_info_no_manufacturer() -> None:
    """Test _map_device_info with no manufacturer."""
    mock_device = MagicMock(spec=VictronVenusDevice)
    mock_device.unique_id = "device_123"
    mock_device.manufacturer = None
    mock_device.name = "Unknown Device"
    mock_device.device_id = "0"
    mock_device.model = "Unknown"
    mock_device.serial_number = None

    installation_id = "12345"

    device_info = Hub._map_device_info(mock_device, installation_id)

    assert device_info.get("manufacturer") == "Victron Energy"
    assert (
        device_info.get("name") == "Unknown Device"
    )  # device_id == "0" uses name only


async def test_unregister_add_entities_callback(
    hass: HomeAssistant, init_integration
) -> None:
    """Test unregistering add entities callback."""
    victron_hub, mock_config_entry = init_integration

    # Inject a sensor before unloading
    await inject_message(victron_hub, "N/123/battery/0/Soc", '{"value": 75}')
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities_before = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities_before) > 0

    # Unload the config entry (which unregisters callbacks)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entities should still be registered (just unavailable)
    entities_after = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities_after) == len(entities_before)
