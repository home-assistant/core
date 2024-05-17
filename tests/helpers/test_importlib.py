"""Tests for the importlib helper."""

import time
from typing import Any
from unittest.mock import patch

import pytest

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


async def test_async_import_module_on_helper(hass: HomeAssistant) -> None:
    """Test importing the importlib helper."""
    module = await importlib.async_import_module(
        hass, "homeassistant.helpers.importlib"
    )
    assert module is importlib
    module = await importlib.async_import_module(
        hass, "homeassistant.helpers.importlib"
    )
    assert module is importlib


async def test_async_import_module_failures(hass: HomeAssistant) -> None:
    """Test importing a module fails."""
    with (
        patch(
            "homeassistant.helpers.importlib.importlib.import_module",
            side_effect=ValueError,
        ),
        pytest.raises(ValueError),
    ):
        await importlib.async_import_module(hass, "test.module")

    mock_module = MockModule()
    # The failure should be not be cached
    with (
        patch(
            "homeassistant.helpers.importlib.importlib.import_module",
            return_value=mock_module,
        ),
    ):
        assert await importlib.async_import_module(hass, "test.module") is mock_module


async def test_async_import_module_failure_caches_module_not_found(
    hass: HomeAssistant,
) -> None:
    """Test importing a module caches ModuleNotFound."""
    with (
        patch(
            "homeassistant.helpers.importlib.importlib.import_module",
            side_effect=ModuleNotFoundError,
        ),
        pytest.raises(ModuleNotFoundError),
    ):
        await importlib.async_import_module(hass, "test.module")

    mock_module = MockModule()
    # The failure should be cached
    with (
        pytest.raises(ModuleNotFoundError),
        patch(
            "homeassistant.helpers.importlib.importlib.import_module",
            return_value=mock_module,
        ),
    ):
        await importlib.async_import_module(hass, "test.module")


@pytest.mark.parametrize("eager_start", [True, False])
async def test_async_import_module_concurrency(
    hass: HomeAssistant, eager_start: bool
) -> None:
    """Test importing a module with concurrency."""
    mock_module = MockModule()

    def _mock_import(name: str, *args: Any) -> MockModule:
        time.sleep(0.1)
        return mock_module

    with patch(
        "homeassistant.helpers.importlib.importlib.import_module",
        _mock_import,
    ):
        task1 = hass.async_create_task(
            importlib.async_import_module(hass, "test.module"), eager_start=eager_start
        )
        task2 = hass.async_create_task(
            importlib.async_import_module(hass, "test.module"), eager_start=eager_start
        )
        module1 = await task1
        module2 = await task2

    assert module1 is mock_module
    assert module2 is mock_module
