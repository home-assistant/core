"""Test helpers."""

import asyncio
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import skyboxremote

from homeassistant.components.sky_remote.const import LEGACY_PORT
from homeassistant.const import CONF_HOST


@pytest.fixture(name="sample_config")
async def get_config_to_integration_load() -> dict[str, Any]:
    """Return configuration.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("sample_config", [{...}])
    """
    return {
        CONF_HOST: "10.0.0.1",
    }


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Stub out setup function."""
    with patch(
        "homeassistant.components.sky_remote.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_remote_control() -> Generator[MagicMock]:
    """Mock skyboxremote library."""
    with patch(
        "homeassistant.components.sky_remote.RemoteControl"
    ) as mock_remote_control:
        instance_mock = MagicMock()
        mock_remote_control.return_value = instance_mock
        return_val = asyncio.Future()
        return_val.set_result(True)
        instance_mock.check_connectable.return_value = return_val

        yield mock_remote_control


@pytest.fixture
def mock_legacy_remote_control() -> Generator[MagicMock]:
    """Mock skyboxremote library."""
    with patch(
        "homeassistant.components.sky_remote.RemoteControl"
    ) as mock_remote_control:
        instance_mock = MagicMock()

        def mock_init(_host, port):
            if port == LEGACY_PORT:
                return_val = asyncio.Future()
                return_val.set_result(True)
                instance_mock.check_connectable.return_value = return_val
            else:
                instance_mock.check_connectable.side_effect = (
                    skyboxremote.SkyBoxConnectionError
                )
            return instance_mock

        mock_remote_control.side_effect = mock_init

        yield mock_remote_control


@pytest.fixture
def mock_remote_control_unconnectable() -> Generator[MagicMock]:
    """Mock skyboxremote library."""
    with patch(
        "homeassistant.components.sky_remote.RemoteControl"
    ) as mock_remote_control:
        instance_mock = MagicMock()
        mock_remote_control.return_value = instance_mock
        instance_mock.check_connectable.side_effect = skyboxremote.SkyBoxConnectionError

        yield mock_remote_control
