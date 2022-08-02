"""Tests for the Aqara cover device."""
from unittest.mock import patch
import aqara_iot.openmq
from .common import mock_start
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_DEVICE_CLASS,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    STATE_CLOSED,
    STATE_OPEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .common import setup_platform


DEVICE_ID = "cover.curtain_lumi_4cf8cdf3c7da659"
DEVICE_UID = "Aqara.lumi.4cf8cdf3c7da659__1.1.85"


async def test_entity_registry(hass: HomeAssistant) -> None:
    """Tests that the devices are registered in the entity registry."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, COVER_DOMAIN)
        entity_registry = er.async_get(hass)

        entry = entity_registry.async_get(DEVICE_ID)
        # print(entry)
        assert entry.unique_id == DEVICE_UID


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the switch attributes are correct."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, COVER_DOMAIN)

        state = hass.states.get(DEVICE_ID)
        print("===========================================")
        print(state)
        assert state.state == STATE_OPEN
        assert state.attributes.get(ATTR_DEVICE_CLASS) == "curtain"


async def test_open(hass: HomeAssistant) -> None:
    """Test the cover can be opened."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, COVER_DOMAIN)

        with patch("aqara_iot.AqaraDeviceManager.send_commands") as mock_command:
            await hass.services.async_call(
                COVER_DOMAIN,
                SERVICE_OPEN_COVER,
                {ATTR_ENTITY_ID: DEVICE_ID},
                blocking=True,
            )
            await hass.async_block_till_done()
            mock_command.assert_called_once()


async def test_close(hass: HomeAssistant) -> None:
    """Test the cover can be closed."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, COVER_DOMAIN)

        with patch("aqara_iot.AqaraDeviceManager.send_commands") as mock_command:
            await hass.services.async_call(
                COVER_DOMAIN,
                SERVICE_CLOSE_COVER,
                {ATTR_ENTITY_ID: DEVICE_ID},
                blocking=True,
            )
            await hass.async_block_till_done()
            mock_command.assert_called_once()
