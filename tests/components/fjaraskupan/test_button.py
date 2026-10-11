"""Test the Fjäråskupan button platform."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fjaraskupan import COMMAND_RESETGREASEFILTER, Device, FjaraskupanWriteError
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.fjaraskupan.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import COOKER_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

ENTITY_ID = "button.fjaraskupan_reset_grease_filter"


@pytest.fixture
async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration and discover a device."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    inject_bluetooth_service_info(hass, COOKER_SERVICE_INFO)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def mock_device() -> Iterator[AsyncMock]:
    """Mock the connection to the device."""

    @asynccontextmanager
    async def _connect(self: Device, ble_device: object) -> AsyncIterator[Device]:
        yield self

    with (
        patch(
            "homeassistant.components.fjaraskupan.coordinator.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch.object(Device, "connect", _connect),
        patch.object(Device, "send_command", AsyncMock()) as send_command,
        patch.object(Device, "update", AsyncMock()),
    ):
        yield send_command


@pytest.mark.usefixtures("setup_entry")
async def test_reset_grease_filter(hass: HomeAssistant, mock_device: AsyncMock) -> None:
    """Test pressing the reset grease filter button."""
    assert hass.states.get(ENTITY_ID)

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_device.assert_awaited_once_with(COMMAND_RESETGREASEFILTER)


@pytest.mark.usefixtures("setup_entry")
async def test_reset_grease_filter_error(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test a write error is raised as a translated error."""
    mock_device.side_effect = FjaraskupanWriteError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    assert exc_info.value.translation_key == "write_error"
