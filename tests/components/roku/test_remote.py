"""The tests for the Roku remote platform."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.remote import (
    DOMAIN as REMOTE_DOMAIN,
    RemoteService,
    RemoteServiceArgument,
)
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import UPNP_SERIAL

MAIN_ENTITY_ID = f"{REMOTE_DOMAIN}.my_roku_3"


async def test_setup(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Test setup with basic config."""
    assert hass.states.get(MAIN_ENTITY_ID)


async def test_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test unique id."""
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
        RemoteService.TURN_OFF,
        {TargetKey.ENTITY_ID: MAIN_ENTITY_ID},
        blocking=True,
    )
    assert mock_roku.remote.call_count == 1
    mock_roku.remote.assert_called_with("poweroff")

    await hass.services.async_call(
        REMOTE_DOMAIN,
        RemoteService.TURN_ON,
        {TargetKey.ENTITY_ID: MAIN_ENTITY_ID},
        blocking=True,
    )
    assert mock_roku.remote.call_count == 2
    mock_roku.remote.assert_called_with("poweron")

    await hass.services.async_call(
        REMOTE_DOMAIN,
        RemoteService.SEND_COMMAND,
        {TargetKey.ENTITY_ID: MAIN_ENTITY_ID, RemoteServiceArgument.COMMAND: ["home"]},
        blocking=True,
    )
    assert mock_roku.remote.call_count == 3
    mock_roku.remote.assert_called_with("home")
