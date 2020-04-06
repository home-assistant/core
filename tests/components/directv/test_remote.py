"""The tests for the DirecTV remote platform."""
from typing import Any, List

from asynctest import patch

from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.components.directv import setup_integration
from tests.test_util.aiohttp import AiohttpClientMocker

ATTR_UNIQUE_ID = "unique_id"
CLIENT_ENTITY_ID = f"{REMOTE_DOMAIN}.client"
MAIN_ENTITY_ID = f"{REMOTE_DOMAIN}.host"
UNAVAILABLE_ENTITY_ID = f"{REMOTE_DOMAIN}.unavailable_client"

# pylint: disable=redefined-outer-name


async def async_send_command(
    hass: HomeAssistantType,
    command: List[str],
    entity_id: Any = ENTITY_MATCH_ALL,
    device: str = None,
    num_repeats: str = None,
    delay_secs: str = None,
) -> None:
    """Send a command to a device."""
    data = {ATTR_COMMAND: command}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if device:
        data[ATTR_DEVICE] = device

    if num_repeats:
        data[ATTR_NUM_REPEATS] = num_repeats

    if delay_secs:
        data[ATTR_DELAY_SECS] = delay_secs

    await hass.services.async_call(REMOTE_DOMAIN, SERVICE_SEND_COMMAND, data)


async def async_turn_on(
    hass: HomeAssistantType, entity_id: Any = ENTITY_MATCH_ALL
) -> None:
    """Turn on device."""
    data = {}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(REMOTE_DOMAIN, SERVICE_TURN_ON, data)


async def async_turn_off(
    hass: HomeAssistantType, entity_id: Any = ENTITY_MATCH_ALL
) -> None:
    """Turn off remote."""
    data = {}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(REMOTE_DOMAIN, SERVICE_TURN_OFF, data)


async def test_setup(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with basic config."""
    await setup_integration(hass, aioclient_mock)
    assert hass.states.get(MAIN_ENTITY_ID)
    assert hass.states.get(CLIENT_ENTITY_ID)
    assert hass.states.get(UNAVAILABLE_ENTITY_ID)


async def test_unique_id(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test unique id."""
    await setup_integration(hass, aioclient_mock)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    main = entity_registry.async_get(MAIN_ENTITY_ID)
    assert main.unique_id == "028877455858"

    client = entity_registry.async_get(CLIENT_ENTITY_ID)
    assert client.unique_id == "2CA17D1CD30X"

    unavailable_client = entity_registry.async_get(UNAVAILABLE_ENTITY_ID)
    assert unavailable_client.unique_id == "9XXXXXXXXXX9"


async def test_main_services(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the different services."""
    await setup_integration(hass, aioclient_mock)

    with patch("directv.DIRECTV.remote") as remote_mock:
        await async_turn_off(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        remote_mock.assert_called_once_with("poweroff", "0")

    with patch("directv.DIRECTV.remote") as remote_mock:
        await async_turn_on(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        remote_mock.assert_called_once_with("poweron", "0")

    with patch("directv.DIRECTV.remote") as remote_mock:
        await async_send_command(hass, ["dash"], MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        remote_mock.assert_called_once_with("dash", "0")
