# start in custom_components directory: pytest hausbus/tests/ --cov=hausbus --cov-branch
import sys
import os

# Pfad zu ~/.homeassistant hinzufügen
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.expanduser("~/.homeassistant"))

import pytest
import asyncio
from homeassistant import data_entry_flow
from homeassistant.config_entries import SOURCE_USER
#from hausbus.const import DOMAIN
from .config_flow import ConfigFlow
from pytest_homeassistant_custom_component.common import MockConfigEntry
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_user_flow_success():
    hass_mock = MagicMock()

    async def dummy_wait(user_input=None):
        return None

    with patch("hausbus.config_flow.HomeServer", return_value=MagicMock()), \
         patch.object(ConfigFlow, "_async_wait_for_device", new=dummy_wait):

        flow = ConfigFlow()
        flow.hass = hass_mock
        flow.hass.async_create_task = asyncio.create_task

        # Flow starten -> Progress
        result = await flow.async_step_user(user_input={})
        assert result["type"] == "progress"

        # Task abwarten -> Progress Done
        await flow._search_task
        result = await flow.async_step_user(user_input={})
        assert result["type"] == "progress_done"  # <---- korrekt

@pytest.mark.asyncio
async def test_user_flow_invalid_input():
    hass_mock = MagicMock()

    async def dummy_wait(user_input=None):
        return None

    with patch("hausbus.config_flow.HomeServer", return_value=MagicMock()), \
         patch.object(ConfigFlow, "_async_wait_for_device", new=dummy_wait):

        flow = ConfigFlow()
        flow.hass = hass_mock
        flow.hass.async_create_task = asyncio.create_task

        # Ungültige Eingaben -> Progress
        result = await flow.async_step_user(user_input={"invalid": "data"})
        assert result["type"] == "progress"

        # Task abwarten -> Progress Done
        await flow._search_task
        result = await flow.async_step_user(user_input={"invalid": "data"})
        assert result["type"] == "progress_done"  # <---- korrekt