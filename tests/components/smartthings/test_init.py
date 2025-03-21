"""Tests for the SmartThings component init module."""

from unittest.mock import AsyncMock

from pysmartthings import (
    Attribute,
    Capability,
    DeviceResponse,
    DeviceStatus,
    SmartThingsSinkError,
)
from pysmartthings.models import Subscription
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.smartthings import EVENT_BUTTON
from homeassistant.components.smartthings.const import CONF_SUBSCRIPTION_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration, trigger_update

from tests.common import MockConfigEntry, load_fixture


async def test_devices(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    device_id = devices.get_devices.return_value[0].device_id

    device = device_registry.async_get_device({(DOMAIN, device_id)})

    assert device is not None
    assert device == snapshot


@pytest.mark.parametrize("device_fixture", ["button"])
async def test_button_event(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test button event."""
    await setup_integration(hass, mock_config_entry)
    events = []

    def capture_event(event: Event) -> None:
        events.append(event)

    hass.bus.async_listen_once(EVENT_BUTTON, capture_event)

    await trigger_update(
        hass,
        devices,
        "c4bdd19f-85d1-4d58-8f9c-e75ac3cf113b",
        Capability.BUTTON,
        Attribute.BUTTON,
        "pushed",
    )

    assert len(events) == 1
    assert events[0] == snapshot


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_create_subscription(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a subscription."""
    assert CONF_SUBSCRIPTION_ID not in mock_config_entry.data

    await setup_integration(hass, mock_config_entry)

    devices.create_subscription.assert_called_once()

    assert (
        mock_config_entry.data[CONF_SUBSCRIPTION_ID]
        == "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )

    devices.subscribe.assert_called_once_with(
        "397678e5-9995-4a39-9d9f-ae6ba310236c",
        "5aaaa925-2be1-4e40-b257-e4ef59083324",
        Subscription.from_json(load_fixture("subscription.json", DOMAIN)),
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_create_subscription_sink_error(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test handling an error when creating a subscription."""
    assert CONF_SUBSCRIPTION_ID not in mock_config_entry.data

    devices.create_subscription.side_effect = SmartThingsSinkError("Sink error")

    await setup_integration(hass, mock_config_entry)

    devices.subscribe.assert_not_called()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert CONF_SUBSCRIPTION_ID not in mock_config_entry.data


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_update_subscription_identifier(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test updating the subscription identifier."""
    await setup_integration(hass, mock_config_entry)

    assert (
        mock_config_entry.data[CONF_SUBSCRIPTION_ID]
        == "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )

    devices.new_subscription_id_callback("abc")

    await hass.async_block_till_done()

    assert mock_config_entry.data[CONF_SUBSCRIPTION_ID] == "abc"


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_stale_subscription_id(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test updating the subscription identifier."""
    mock_config_entry.add_to_hass(hass)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_SUBSCRIPTION_ID: "test"},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        mock_config_entry.data[CONF_SUBSCRIPTION_ID]
        == "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )
    devices.delete_subscription.assert_called_once_with("test")


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_remove_subscription_identifier(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing the subscription identifier."""
    await setup_integration(hass, mock_config_entry)

    assert (
        mock_config_entry.data[CONF_SUBSCRIPTION_ID]
        == "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )

    devices.new_subscription_id_callback(None)

    await hass.async_block_till_done()

    assert mock_config_entry.data[CONF_SUBSCRIPTION_ID] is None


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_max_connections_handling(
    hass: HomeAssistant, devices: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test handling reaching max connections."""
    await setup_integration(hass, mock_config_entry)

    assert (
        mock_config_entry.data[CONF_SUBSCRIPTION_ID]
        == "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )

    devices.create_subscription.side_effect = SmartThingsSinkError("Sink error")

    devices.max_connections_reached_callback()

    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_unloading(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    devices.delete_subscription.assert_called_once_with(
        "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )
    # Deleting the subscription automatically deletes the subscription ID
    devices.new_subscription_id_callback(None)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_config_entry.data[CONF_SUBSCRIPTION_ID] is None


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_shutdown(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test shutting down Home Assistant."""
    await setup_integration(hass, mock_config_entry)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    devices.delete_subscription.assert_called_once_with(
        "f5768ce8-c9e5-4507-9020-912c0c60e0ab"
    )
    # Deleting the subscription automatically deletes the subscription ID
    devices.new_subscription_id_callback(None)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_SUBSCRIPTION_ID] is None


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_removing_stale_devices(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing stale devices."""
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "aaa-bbb-ccc")},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not device_registry.async_get_device({(DOMAIN, "aaa-bbb-ccc")})


async def test_hub_via_device(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_smartthings: AsyncMock,
) -> None:
    """Test hub with child devices."""
    mock_smartthings.get_devices.return_value = DeviceResponse.from_json(
        load_fixture("devices/hub.json", DOMAIN)
    ).items
    mock_smartthings.get_device_status.side_effect = [
        DeviceStatus.from_json(
            load_fixture(f"device_status/{fixture}.json", DOMAIN)
        ).components
        for fixture in ("hub", "multipurpose_sensor")
    ]
    await setup_integration(hass, mock_config_entry)

    hub_device = device_registry.async_get_device(
        {(DOMAIN, "074fa784-8be8-4c70-8e22-6f5ed6f81b7e")}
    )
    assert hub_device == snapshot
    assert (
        device_registry.async_get_device(
            {(DOMAIN, "374ba6fa-5a08-4ea2-969c-1fa43d86e21f")}
        ).via_device_id
        == hub_device.id
    )
