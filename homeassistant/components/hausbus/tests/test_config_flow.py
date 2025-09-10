"""Tests for the Hausbus config flow integration."""
# start in custom_components directory: pytest hausbus/tests/ --cov=hausbus --cov-branch
import os
import sys

# Pfad zu ~/.homeassistant hinzufügen
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.expanduser("~/.homeassistant"))

import asyncio
from unittest.mock import MagicMock, patch

import pytest

# from hausbus.const import DOMAIN
from .config_flow import ConfigFlow


@pytest.mark.asyncio
async def test_user_flow_success():
    """test successful user flow."""
    hass_mock = MagicMock()

    async def dummy_wait(user_input=None):
        return None

    with (
        patch("hausbus.config_flow.HomeServer", return_value=MagicMock()),
        patch.object(ConfigFlow, "_async_wait_for_device", new=dummy_wait),
    ):

        flow = ConfigFlow()
        flow.hass = hass_mock
        flow.hass.async_create_task = asyncio.create_task

        # Flow starten -> Progress
        result = await flow.async_step_user(user_input={})
        assert result["type"] == "progress"

        # Task abwarten -> Progress Done
        await flow._search_task # noqa: SLF001
        result = await flow.async_step_user(user_input={})
        assert result["type"] == "progress_done"  # <---- korrekt


@pytest.mark.asyncio
async def test_user_flow_invalid_input():
    """test invalid user flow."""
    hass_mock = MagicMock()

    async def dummy_wait(user_input=None):
        return None

    with (
        patch("hausbus.config_flow.HomeServer", return_value=MagicMock()),
        patch.object(ConfigFlow, "_async_wait_for_device", new=dummy_wait),
    ):

        flow = ConfigFlow()
        flow.hass = hass_mock
        flow.hass.async_create_task = asyncio.create_task

        # Ungültige Eingaben -> Progress
        result = await flow.async_step_user(user_input={"invalid": "data"})
        assert result["type"] == "progress"

        # Task abwarten -> Progress Done
        await flow._search_task # noqa: SLF001
        result = await flow.async_step_user(user_input={"invalid": "data"})
        assert result["type"] == "progress_done"  # <---- korrekt



# flake8: noqa: D103,D104
# pylint: skip-file
# mypy: ignore-errors