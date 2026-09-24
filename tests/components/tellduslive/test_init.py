"""Tests for the TelldusLive integration setup."""

from unittest.mock import MagicMock

from homeassistant.components.tellduslive import NEW_CLIENT_TASK
from homeassistant.components.tellduslive.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import DEVICE_ID, HUB_ID

from tests.common import MockConfigEntry


async def test_device_via_device_links(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test that a discovered device links to its hub via via_device_id."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    # Hubs and devices are registered from a background task spawned by setup.
    await hass.data[NEW_CLIENT_TASK]
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    hub_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, HUB_ID), mock_config_entry.entry_id
    )
    assert hub_device is not None

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), mock_config_entry.entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id == hub_device.id

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_device_added_without_hub(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test a device is still added, unlinked, when its hub is not registered."""
    # A failed clients/list request yields an empty hub list, so no hub is registered.
    mock_tellduslive.get_clients.return_value = []
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.data[NEW_CLIENT_TASK]
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, HUB_ID), mock_config_entry.entry_id
        )
        is None
    )

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), mock_config_entry.entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id is None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
