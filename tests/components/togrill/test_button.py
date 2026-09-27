"""Test buttons for ToGrill integration."""

from unittest.mock import Mock

import pytest
from syrupy.assertion import SnapshotAssertion
from togrill_bluetooth.packets import PacketA5Write

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import TOGRILL_SERVICE_INFO, setup_entry

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
) -> None:
    """Test the buttons."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.BUTTON])

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


async def test_press(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
) -> None:
    """Test pressing the silence button."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.BUTTON])

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        target={
            ATTR_ENTITY_ID: "button.pro_05_silence_alarm",
        },
        blocking=True,
    )

    mock_client.write.assert_any_call(PacketA5Write())


async def test_press_disconnected(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
) -> None:
    """Test pressing the button while disconnected raises."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.BUTTON])

    mock_client.is_connected = False

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            target={
                ATTR_ENTITY_ID: "button.pro_05_silence_alarm",
            },
            blocking=True,
        )
