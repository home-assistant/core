"""The tests for the Roku remote platform."""
from unittest.mock import MagicMock

from homeassistant.components.remote import (
    ATTR_COMMAND,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.roku import UPNP_SERIAL

MAIN_ENTITY_ID = f"{REMOTE_DOMAIN}.my_roku_3"

# pylint: disable=redefined-outer-name


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
