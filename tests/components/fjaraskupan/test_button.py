"""Test the Fjäråskupan button platform."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

from fjaraskupan import (
    ANNOUNCE_MANUFACTURER,
    COMMAND_RESETGREASEFILTER,
    DEVICE_NAME,
    Device,
    FjaraskupanWriteError,
)
from habluetooth import BluetoothServiceInfo
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.fjaraskupan.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import COOKER_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

BUTTON_ENTITY_ID = "button.fjaraskupan_reset_grease_filter"
GREASE_FILTER_ENTITY_ID = "binary_sensor.fjaraskupan_grease_filter"

GREASE_FILTER_FULL_SERVICE_INFO = BluetoothServiceInfo(
    address=COOKER_SERVICE_INFO.address,
    name=DEVICE_NAME,
    service_uuids=[],
    rssi=-60,
    manufacturer_data={ANNOUNCE_MANUFACTURER: b"ODFJAR\x01\x02\x00\x01\x00\x30\x04"},
    service_data={},
    source="local",
)


@pytest.fixture
async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration with a device reporting a full grease filter."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    inject_bluetooth_service_info(hass, COOKER_SERVICE_INFO)
    await hass.async_block_till_done()
    inject_bluetooth_service_info(hass, GREASE_FILTER_FULL_SERVICE_INFO)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def mock_send_command() -> Iterator[AsyncMock]:
    """Mock the connection to the device."""

    @asynccontextmanager
    async def _connect(self: Device, ble_device: object) -> AsyncIterator[Device]:
        yield self

    async def _update(self: Device) -> None:
        self.state = replace(self.state, grease_filter_full=False)

    with (
        patch(
            "homeassistant.components.fjaraskupan.coordinator.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch.object(Device, "connect", _connect),
        patch.object(Device, "send_command", AsyncMock()) as send_command,
        patch.object(Device, "update", _update),
    ):
        yield send_command


@pytest.mark.usefixtures("setup_entry")
async def test_reset_grease_filter(
    hass: HomeAssistant, mock_send_command: AsyncMock
) -> None:
    """Test pressing the button resets the filter and refreshes the state."""
    state = hass.states.get(GREASE_FILTER_ENTITY_ID)
    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: BUTTON_ENTITY_ID}, blocking=True
    )

    mock_send_command.assert_awaited_once_with(COMMAND_RESETGREASEFILTER)
    state = hass.states.get(GREASE_FILTER_ENTITY_ID)
    assert state
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("setup_entry")
async def test_reset_grease_filter_error(
    hass: HomeAssistant, mock_send_command: AsyncMock
) -> None:
    """Test a write error is raised as a translated error."""
    mock_send_command.side_effect = FjaraskupanWriteError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: BUTTON_ENTITY_ID},
            blocking=True,
        )
    assert exc_info.value.translation_key == "write_error"
    state = hass.states.get(GREASE_FILTER_ENTITY_ID)
    assert state
    assert state.state == STATE_ON
