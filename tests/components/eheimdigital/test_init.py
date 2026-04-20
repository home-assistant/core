"""Tests for the init module."""

from unittest.mock import AsyncMock, MagicMock, patch

from eheimdigital.types import EheimDeviceType, EheimDigitalClientError

from homeassistant.components.eheimdigital.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import init_integration

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_dynamic_entities(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test dynamic adding of entities."""
    mock_config_entry.add_to_hass(hass)
    heater_data = eheimdigital_hub_mock.return_value.devices[
        "00:00:00:00:00:02"
    ].heater_data
    eheimdigital_hub_mock.return_value.devices["00:00:00:00:00:02"].heater_data = None
    with (
        patch(
            "homeassistant.components.eheimdigital.coordinator.asyncio.Event",
            new=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    for device in eheimdigital_hub_mock.return_value.devices:
        await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
            device, eheimdigital_hub_mock.return_value.devices[device].device_type
        )
        await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            DOMAIN, Platform.NUMBER, "mock_heater_night_temperature_offset"
        )
        is None
    )

    eheimdigital_hub_mock.return_value.devices[
        "00:00:00:00:00:02"
    ].heater_data = heater_data

    await eheimdigital_hub_mock.call_args.kwargs["receive_callback"]()

    assert hass.states.get("number.mock_heater_night_temperature_offset").state == str(
        eheimdigital_hub_mock.return_value.devices[
            "00:00:00:00:00:02"
        ].night_temperature_offset
    )


async def test_remove_device(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test removing a device."""
    assert await async_setup_component(hass, "config", {})

    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:01", EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    await hass.async_block_till_done()

    mac_address: str = eheimdigital_hub_mock.return_value.main.mac_address

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac_address)},
    )
    assert device_entry is not None

    hass_client = await hass_ws_client(hass)

    # Do not allow to delete a connected device
    response = await hass_client.remove_device(
        device_entry.id, mock_config_entry.entry_id
    )
    assert not response["success"]

    eheimdigital_hub_mock.return_value.devices = {}

    # Allow to delete a not connected device
    response = await hass_client.remove_device(
        device_entry.id, mock_config_entry.entry_id
    )
    assert response["success"]


async def test_entry_setup_error(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test errors on setting up the config entry."""

    eheimdigital_hub_mock.return_value.connect.side_effect = EheimDigitalClientError()
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
