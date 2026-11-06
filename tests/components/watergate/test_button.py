"""Tests for the Watergate button platform."""

from collections.abc import Generator

import pytest
from pytest_homeassistant.common import (
    AsyncMock,
    MockConfigEntry,
    patch,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from watergate_local_api import WatergateApiException, WatergateIndeterminateError

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration

ENTITY_ID = "button.sonic_reboot"


@pytest.mark.usefixtures("mock_watergate_client")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
) -> None:
    """Test the button entities and their registry entries."""
    with patch("homeassistant.components.watergate.PLATFORMS", [Platform.BUTTON]):
        await init_integration(hass, mock_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


async def test_reboot_press(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """Pressing the button sends a reboot to the device."""
    await init_integration(hass, mock_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_watergate_client.async_reboot.assert_awaited_once_with()


async def test_reboot_outcome_unknown_is_not_an_error(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """A lost response (device rebooting) is expected and must not raise."""
    await init_integration(hass, mock_entry)
    mock_watergate_client.async_reboot.side_effect = WatergateIndeterminateError(
        "outcome unknown"
    )

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_watergate_client.async_reboot.assert_awaited_once_with()


async def test_reboot_failure(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """A definite API failure surfaces as HomeAssistantError."""
    await init_integration(hass, mock_entry)
    mock_watergate_client.async_reboot.side_effect = WatergateApiException("boom")

    with pytest.raises(HomeAssistantError, match="Failed to reboot the device"):
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )

    mock_watergate_client.async_reboot.assert_awaited_once_with()
