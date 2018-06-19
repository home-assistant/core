"""Tests for HomematicIP Cloud config flow."""
import asyncio
from unittest.mock import Mock, patch

import aiohue
import pytest
import voluptuous as vol

from homeassistant.components.homematicip_cloud import config_flow, const

from tests.common import MockConfigEntry, mock_coro

async def test_flow_works(hass, aioclient_mock):
    """Test config flow ."""
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass
    await flow.async_step_init()
