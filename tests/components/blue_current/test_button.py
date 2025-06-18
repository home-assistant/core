"""The tests for Blue Current buttons."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.blue_current import DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform

charge_point_buttons = ["stop_charge_session", "reset", "reboot"]


async def test_buttons_created(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test if all buttons are created."""
    await init_integration(hass, config_entry, Platform.BUTTON)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.freeze_time("2023-01-13 12:00:00+00:00")
async def test_charge_point_buttons(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the underlying charge point buttons."""
    await init_integration(hass, config_entry, Platform.BUTTON)

    for button in charge_point_buttons:
        state = hass.states.get(f"button.101_{button}")
        assert state is not None
        assert state.state == STATE_UNKNOWN

        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: f"button.101_{button}"},
            blocking=True,
        )

        state = hass.states.get(f"button.101_{button}")
        assert state
        assert state.state == "2023-01-13T12:00:00+00:00"


async def test_start_charging_service(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the start charing button service when a charging card is provided."""
    integration = await init_integration(hass, config_entry, Platform.BUTTON)
    client = integration[0]

    await hass.services.async_call(
        DOMAIN,
        "start_charge_session",
        {
            "entity_id": "button.101_start_charge_session",
            "charging_card_id": "TEST_CARD",
        },
        blocking=True,
    )

    client.start_session.assert_called_once_with("101", "TEST_CARD")


async def test_start_charging_service_without_card(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the start charing button service when no charging card is provided."""
    integration = await init_integration(hass, config_entry, Platform.BUTTON)
    client = integration[0]

    await hass.services.async_call(
        DOMAIN,
        "start_charge_session",
        {"entity_id": "button.101_start_charge_session"},
        blocking=True,
    )

    client.start_session.assert_called_once_with("101", "BCU-APP")
