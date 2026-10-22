"""Test the Advantage Air Initialization."""

from unittest.mock import AsyncMock

from advantage_air import ApiError
import pytest

from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import add_mock_config, patch_get


async def test_async_setup_entry(hass: HomeAssistant, mock_get: AsyncMock) -> None:
    """Test a successful setup entry and unload."""

    entry = await add_mock_config(hass)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_get")
@pytest.mark.parametrize(
    "child_identifier",
    [
        "uniqueid-ac1",  # AC device
        "uniqueid-100",  # myLights light device
        "uniqueid-203",  # myThings device
    ],
)
async def test_child_devices_via_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    child_identifier: str,
) -> None:
    """Test child devices link to the system device via via_device_id."""

    entry = await add_mock_config(hass)

    parent = device_registry.async_get_device_by_identifier(
        (DOMAIN, "uniqueid"), entry.entry_id
    )
    assert parent is not None

    child = device_registry.async_get_device_by_identifier(
        (DOMAIN, child_identifier), entry.entry_id
    )
    assert child is not None
    assert child.via_device_id == parent.id


async def test_async_setup_entry_failure(hass: HomeAssistant) -> None:
    """Test a unsuccessful setup entry."""

    with patch_get(side_effect=ApiError):
        entry = await add_mock_config(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
