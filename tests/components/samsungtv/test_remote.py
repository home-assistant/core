"""The tests for the SamsungTV remote platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.remote import (
    ATTR_COMMAND,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_samsungtv_entry
from .test_media_player import MOCK_ENTRYDATA_ENCRYPTED_WS

ENTITY_ID = f"{REMOTE_DOMAIN}.fake"


async def test_setup(hass: HomeAssistant) -> None:
    """Test setup with basic config."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)
    assert hass.states.get(ENTITY_ID)


async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique id."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    entity_registry = er.async_get(hass)

    main = entity_registry.async_get(ENTITY_ID)
    assert main.unique_id == "any"


@pytest.mark.usefixtures("rest_api")
async def test_main_services(hass: HomeAssistant) -> None:
    """Test the different services."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVEncryptedBridge.async_power_off"
    ) as remote_mock:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        remote_mock.assert_called_once()

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVEncryptedBridge.async_send_keys"
    ) as remote_mock:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: ["dash"]},
            blocking=True,
        )
        remote_mock.assert_called_once_with(["dash"])
