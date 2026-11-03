"""Tests for Atomberg smart lock entities."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.atomberg.api import AtombergConnectionError
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

DEVICE_ID = "a4cf12999999"
BUTTON = "button.front_door_generate_guest_pin"
NOTIFY = "homeassistant.components.atomberg.button.persistent_notification.async_create"


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        ("sensor.front_door_battery", "80"),
        ("sensor.front_door_unlock_count", "42"),
        ("sensor.front_door_firmware_version", "1.2.3"),
    ],
)
@pytest.mark.usefixtures("mock_client")
async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected: str,
) -> None:
    """Test lock sensors read from the device state."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state == expected


@pytest.mark.usefixtures("mock_client")
async def test_no_lock_entity_is_created(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test no lock or unlock control is offered, as the API does not allow it."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.async_entity_ids("lock") == []


async def test_guest_pin_is_time_limited_and_not_stored(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the PIN gets a 4 hour window, reaches a notification, and no state."""
    freezer.move_to("2026-11-03 10:00:00+00:00")
    await setup_integration(hass, mock_config_entry)

    with patch(NOTIFY) as notify:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: BUTTON}, blocking=True
        )

    start = 1793700000
    mock_client.async_get_guest_pin.assert_awaited_once_with(
        DEVICE_ID, start, start + 4 * 3600
    )
    assert "482915" in notify.call_args.args[1]
    assert all(
        "482915" not in str(state.as_dict()) for state in hass.states.async_all()
    )


async def test_guest_pin_without_time_window(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test other lock series request a PIN without a time window."""
    mock_client.async_get_devices.return_value = [
        replace(device, series="other_lock") if device.device_type == "lock" else device
        for device in mock_client.async_get_devices.return_value
    ]
    await setup_integration(hass, mock_config_entry)

    with patch(NOTIFY):
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: BUTTON}, blocking=True
        )

    mock_client.async_get_guest_pin.assert_awaited_once_with(DEVICE_ID, None, None)


async def test_guest_pin_error(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test API errors surface and no notification is created."""
    mock_client.async_get_guest_pin.side_effect = AtombergConnectionError("boom")
    await setup_integration(hass, mock_config_entry)

    with patch(NOTIFY) as notify, pytest.raises(HomeAssistantError, match="boom"):
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: BUTTON}, blocking=True
        )

    notify.assert_not_called()
