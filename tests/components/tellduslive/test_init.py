"""Tests for the TelldusLive integration setup."""

from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant.components.tellduslive.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .conftest import DEVICE_ID, HUB_ID

from tests.common import MockConfigEntry, async_fire_time_changed


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
    await mock_config_entry.runtime_data.setup_task
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
    assert hass.states.async_all("switch")

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert all(
        state.state == STATE_UNAVAILABLE for state in hass.states.async_all("switch")
    )


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
    await mock_config_entry.runtime_data.setup_task
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


async def test_setup_not_authorized(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test setup fails when the session is not authorized."""
    mock_tellduslive.is_authorized = False
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "Authentication with Telldus Live failed"


async def test_no_polling_after_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test an update finishing after unload does not schedule another."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await mock_config_entry.runtime_data.setup_task
    await hass.async_block_till_done()
    client = mock_config_entry.runtime_data.client

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    # Simulate an update that was in flight while the entry unloaded.
    await client.update()
    mock_tellduslive.update.reset_mock()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    mock_tellduslive.update.assert_not_called()
