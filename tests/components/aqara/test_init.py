"""Tests for the aqara module."""
from unittest.mock import patch

import aqara_iot.openmq

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant

from .common import mock_start, setup_platform


async def test_change_settings(hass: HomeAssistant) -> None:
    """Test change_setting service."""
    await setup_platform(hass, SWITCH_DOMAIN)


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the aqara entry."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, SWITCH_DOMAIN)
