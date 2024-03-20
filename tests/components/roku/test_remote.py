"""The tests for the Roku remote platform."""

from unittest.mock import MagicMock, call

from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import UPNP_SERIAL

from tests.common import MockConfigEntry

MAIN_ENTITY_ID = f"{REMOTE_DOMAIN}.my_roku_3"


async def test_setup(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Test setup with basic config."""
    assert hass.states.get(MAIN_ENTITY_ID)


async def test_unique_id(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test unique id."""
    entity_registry = er.async_get(hass)

    main = entity_registry.async_get(MAIN_ENTITY_ID)
    assert main.unique_id == UPNP_SERIAL


async def test_main_services(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_roku: MagicMock,
) -> None:
    """Test platform services."""
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
        blocking=True,
    )
    assert mock_roku.remote.call_count == 1
    mock_roku.remote.assert_called_with("poweroff")

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
        blocking=True,
    )
    assert mock_roku.remote.call_count == 2
    mock_roku.remote.assert_called_with("poweron")

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_COMMAND: ["home"]},
        blocking=True,
    )
    assert mock_roku.remote.call_count == 3
    mock_roku.remote.assert_called_with("home")

    mock_roku.remote.reset_mock()
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            ATTR_ENTITY_ID: MAIN_ENTITY_ID,
            ATTR_COMMAND: ["left", "right"]
            ATTR_NUM_REPEATS: 2,
            ATTR_DELAY_SECS: 1
        },
        blocking=True,
    )
    assert mock_roku.remote.call_count == 4
    mock_roku.remote.assert_has_calls([
        call("left"),
        call("right"),
        call("left"),
        call("right"),
    ])
