"""Test init of ecovacs."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from deebot_client.capabilities import Capabilities
from deebot_client.exceptions import DeebotError, InvalidAuthenticationError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .const import IMPORT_DATA

from tests.common import MockConfigEntry


@pytest.mark.usefixtures(
    "mock_authenticator", "mock_mqtt_client", "mock_device_execute"
)
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    with patch(
        "homeassistant.components.ecovacs.EcovacsController",
        autospec=True,
    ):
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert DOMAIN not in hass.data
        controller = mock_config_entry.runtime_data
        assert isinstance(controller, EcovacsController)
        controller.initialize.assert_called_once()

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        controller.teardown.assert_called_once()

        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.fixture
def mock_api_client(mock_authenticator: Mock) -> Mock:
    """Mock the API client."""
    with patch(
        "homeassistant.components.ecovacs.controller.ApiClient",
        autospec=True,
    ) as mock_api_client:
        yield mock_api_client.return_value


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: Mock,
) -> None:
    """Test the Ecovacs configuration entry not ready."""
    mock_api_client.get_devices.side_effect = DeebotError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: Mock,
) -> None:
    """Test auth error during setup."""
    mock_api_client.get_devices.side_effect = InvalidAuthenticationError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("config", "config_entries_expected"),
    [
        ({}, 0),
        ({DOMAIN: IMPORT_DATA.copy()}, 1),
    ],
    ids=["no_config", "import_config"],
)
async def test_async_setup_import(
    hass: HomeAssistant,
    config: dict[str, Any],
    config_entries_expected: int,
    mock_setup_entry: AsyncMock,
    mock_authenticator_authenticate: AsyncMock,
    mock_mqtt_client: Mock,
) -> None:
    """Test async_setup config import."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == config_entries_expected
    assert mock_setup_entry.call_count == config_entries_expected
    assert mock_authenticator_authenticate.call_count == config_entries_expected
    assert mock_mqtt_client.verify_config.call_count == config_entries_expected


async def test_devices_in_dr(
    device_registry: dr.DeviceRegistry,
    controller: EcovacsController,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all devices are in the device registry."""
    for device in controller.devices(Capabilities):
        assert (
            device_entry := device_registry.async_get_device(
                identifiers={(DOMAIN, device.device_info["did"])}
            )
        )
        assert device_entry == snapshot(name=device.device_info["did"])


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    ("device_fixture", "entities"),
    [
        ("yna5x1", 26),
        ("5xu9h3", 24),
    ],
)
async def test_all_entities_loaded(
    hass: HomeAssistant,
    device_fixture: str,
    entities: int,
) -> None:
    """Test that all entities are loaded together."""
    assert (
        hass.states.async_entity_ids_count() == entities
    ), f"loaded entities for {device_fixture}: {hass.states.async_entity_ids()}"
