"""Test init of acaia integration."""

from datetime import timedelta
from unittest.mock import MagicMock

from aioacaia.exceptions import AcaiaDeviceNotFound, AcaiaError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.acaia.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "exception", [AcaiaError, AcaiaDeviceNotFound("Boom"), TimeoutError]
)
async def test_update_exception_leads_to_active_disconnect(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test scale gets disconnected on exception."""

    mock_scale.connect.side_effect = exception
    mock_scale.connected = False

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_scale.device_disconnected_handler.assert_called_once()


async def test_device(
    mock_scale: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the device from registry."""

    device = device_registry.async_get_device({(DOMAIN, mock_scale.mac)})
    assert device
    assert device == snapshot
