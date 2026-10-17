"""Tests for the Acmeda integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import aiopulse
import pytest

from homeassistant.components.acmeda.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.fixture
def mock_roller() -> MagicMock:
    """Return a mocked Acmeda roller."""
    roller = MagicMock()
    roller.id = 1234567890123
    roller.name = "Roller"
    roller.battery = 50
    roller.type = 1
    roller.closed_percent = 50
    return roller


@pytest.fixture
def mock_hub(mock_roller: MagicMock) -> Generator[MagicMock]:
    """Mock the aiopulse Hub client."""
    with patch("homeassistant.components.acmeda.hub.aiopulse.Hub") as hub_class:
        hub = hub_class.return_value
        hub.id = "hub-id"
        hub.host = "127.0.0.1"
        hub.rollers = {mock_roller.id: mock_roller}
        hub.run = AsyncMock()
        hub.stop = AsyncMock()
        yield hub


async def test_update_devices_renames_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
) -> None:
    """Test a roller rename is propagated to the device registry."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The integration subscribes a callback which the hub invokes once it has
    # fetched roller updates; grab it and simulate the hub reporting an update.
    notify_update = mock_hub.callback_subscribe.call_args[0][0]
    await notify_update(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(mock_roller.id)), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Roller"

    mock_roller.name = "Living room blind"
    await notify_update(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(mock_roller.id)), mock_config_entry.entry_id
    )
    assert device.name == "Living room blind"


@pytest.mark.usefixtures("mock_hub")
async def test_unload_hub_reset_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading fails when the hub cannot be reset."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # A hub without an API reports that it could not be reset
    mock_config_entry.runtime_data.api = None

    assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert mock_config_entry.reason == "Could not reset the Acmeda hub while unloading"
