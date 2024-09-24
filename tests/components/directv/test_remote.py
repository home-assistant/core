"""The tests for the DirecTV remote platform."""

from unittest.mock import patch

from homeassistant.components.remote import (
    ATTR_COMMAND,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.test_util.aiohttp import AiohttpClientMocker

ATTR_UNIQUE_ID = "unique_id"
CLIENT_ENTITY_ID = f"{REMOTE_DOMAIN}.client"
MAIN_ENTITY_ID = f"{REMOTE_DOMAIN}.host"
UNAVAILABLE_ENTITY_ID = f"{REMOTE_DOMAIN}.unavailable_client"


async def test_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test setup with basic config."""
    await setup_integration(hass, aioclient_mock)
    assert hass.states.get(MAIN_ENTITY_ID)
    assert hass.states.get(CLIENT_ENTITY_ID)
    assert hass.states.get(UNAVAILABLE_ENTITY_ID)


async def test_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test unique id."""
    await setup_integration(hass, aioclient_mock)

    main = entity_registry.async_get(MAIN_ENTITY_ID)
    assert main.unique_id == "028877455858"

    client = entity_registry.async_get(CLIENT_ENTITY_ID)
    assert client.unique_id == "2CA17D1CD30X"

    unavailable_client = entity_registry.async_get(UNAVAILABLE_ENTITY_ID)
    assert unavailable_client.unique_id == "9XXXXXXXXXX9"


async def test_main_services(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the different services."""
    await setup_integration(hass, aioclient_mock)

    with patch("directv.DIRECTV.remote") as remote_mock:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )
        remote_mock.assert_called_once_with("poweroff", "0")

    with patch("directv.DIRECTV.remote") as remote_mock:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )
        remote_mock.assert_called_once_with("poweron", "0")

    with patch("directv.DIRECTV.remote") as remote_mock:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_COMMAND: ["dash"]},
            blocking=True,
        )
        remote_mock.assert_called_once_with("dash", "0")
