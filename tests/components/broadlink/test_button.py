"""Tests for Broadlink buttons."""

import broadlink_async.exceptions as blke
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import get_device

ENTITY_ID = "button.guest_room_sync_time"


async def test_sync_time_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the button sets the thermostat clock to the local time."""
    await hass.config.async_set_time_zone("Europe/Warsaw")
    freezer.move_to("2026-10-21 12:34:56+00:00")
    device = get_device("Guest room")
    mock_setup = await device.setup_entry(hass)

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{device.mac}-sync_time"
    mock_setup.api.set_time.assert_not_awaited()

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_setup.api.set_time.assert_awaited_once_with(
        hour=14, minute=34, second=56, day=3
    )


async def test_sync_time_button_failure(hass: HomeAssistant) -> None:
    """Test a failure to set the clock is reported."""
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    mock_api.set_time.side_effect = blke.NetworkTimeoutError()
    await device.setup_entry(hass, mock_api=mock_api)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    assert exc_info.value.translation_key == "sync_time_failed"
