"""Tests for the PTDevices coordinator."""

from unittest.mock import AsyncMock

from aioptdevices import (
    PTDevicesForbiddenError,
    PTDevicesParseError,
    PTDevicesRequestError,
    PTDevicesUnauthorizedError,
)
from aioptdevices.interface import PTDevicesResponse
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.ptdevices.const import DOMAIN
from homeassistant.components.ptdevices.coordinator import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

GARDEN_DEVICE_ID = "C0FFEFC0FFEF"
GARDEN_IDENTIFIER = (DOMAIN, f"1234_{GARDEN_DEVICE_ID}")
GARDEN_ENTITY_ID = "sensor.garden_rain_barrel_level_percent"


async def _refresh(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger a coordinator update."""
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _without_garden(response: PTDevicesResponse) -> PTDevicesResponse:
    """Return the response with the garden device removed from the body."""
    body = {k: v for k, v in response["body"].items() if k != GARDEN_DEVICE_ID}
    return PTDevicesResponse(code=200, body=body)


async def test_failed_device_is_not_purged(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_ptdevices_interface: AsyncMock,
    mock_ptdevices_config_entry: MockConfigEntry,
    mock_ptdevices_level: PTDevicesResponse,
) -> None:
    """Test a device that fails to parse is kept and recovers on the next update."""
    await setup_integration(hass, mock_ptdevices_config_entry)
    assert hass.states.get(GARDEN_ENTITY_ID).state != STATE_UNAVAILABLE

    failed_response = _without_garden(mock_ptdevices_level)
    failed_response["failed"] = {GARDEN_DEVICE_ID}
    mock_ptdevices_interface.get_data.return_value = failed_response
    await _refresh(hass, freezer)

    assert device_registry.async_get_device_by_identifier(
        GARDEN_IDENTIFIER, mock_ptdevices_config_entry.entry_id
    )
    assert hass.states.get(GARDEN_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_ptdevices_interface.get_data.return_value = mock_ptdevices_level
    await _refresh(hass, freezer)

    assert hass.states.get(GARDEN_ENTITY_ID).state != STATE_UNAVAILABLE


async def test_removed_device_is_purged(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_ptdevices_interface: AsyncMock,
    mock_ptdevices_config_entry: MockConfigEntry,
    mock_ptdevices_level: PTDevicesResponse,
) -> None:
    """Test a device no longer in the account is removed."""
    await setup_integration(hass, mock_ptdevices_config_entry)
    assert device_registry.async_get_device_by_identifier(
        GARDEN_IDENTIFIER, mock_ptdevices_config_entry.entry_id
    )

    mock_ptdevices_interface.get_data.return_value = _without_garden(
        mock_ptdevices_level
    )
    await _refresh(hass, freezer)

    assert not device_registry.async_get_device_by_identifier(
        GARDEN_IDENTIFIER, mock_ptdevices_config_entry.entry_id
    )


@pytest.mark.parametrize(
    "exception",
    [
        PTDevicesRequestError,
        PTDevicesUnauthorizedError,
        PTDevicesForbiddenError,
        PTDevicesParseError,
    ],
)
async def test_update_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_ptdevices_interface: AsyncMock,
    mock_ptdevices_config_entry: MockConfigEntry,
    mock_ptdevices_level: PTDevicesResponse,
    exception: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test library errors mark entities unavailable until the next good update."""
    await setup_integration(hass, mock_ptdevices_config_entry)
    caplog.clear()

    mock_ptdevices_interface.get_data.side_effect = exception
    await _refresh(hass, freezer)

    assert "Error fetching ptdevices data:" in caplog.text
    assert "Unexpected error fetching ptdevices data" not in caplog.text
    assert hass.states.get(GARDEN_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_ptdevices_interface.get_data.side_effect = None
    mock_ptdevices_interface.get_data.return_value = mock_ptdevices_level
    await _refresh(hass, freezer)

    assert hass.states.get(GARDEN_ENTITY_ID).state != STATE_UNAVAILABLE
