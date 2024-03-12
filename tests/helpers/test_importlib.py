"""Tests for the importlib helper."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import importlib

from tests.common import MockModule


async def test_async_import_module(hass: HomeAssistant) -> None:
    """Test importing a module."""
    mock_module = MockModule()
    with patch(
        "homeassistant.helpers.importlib.importlib.import_module",
        return_value=mock_module,
    ):
        module = await importlib.async_import_module(hass, "test.module")

    assert module is mock_module


async def test_async_import_module_concurrency(hass: HomeAssistant) -> None:
    """Test importing a module."""
    mock_module = MockModule()

    with patch(
        "homeassistant.helpers.importlib.importlib.import_module",
        return_value=mock_module,
    ):
        task1 = hass.async_create_task(
            importlib.async_import_module(hass, "test.module")
        )
        task2 = hass.async_create_task(
            importlib.async_import_module(hass, "test.module")
        )
        module1 = await task1
        module2 = await task2

    assert module1 is mock_module
    assert module2 is mock_module
