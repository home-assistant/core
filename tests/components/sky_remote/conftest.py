"""Test helpers."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.sky_remote.const import CONF_LEGACY_CONTROL_PORT
from homeassistant.const import CONF_HOST, CONF_NAME


@pytest.fixture(name="sample_config")
async def get_config_to_integration_load() -> dict[str, Any]:
    """Return configuration.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("sample_config", [{...}])
    """
    return {
        CONF_HOST: "10.0.0.1",
        CONF_NAME: "Living Room Sky Box",
        CONF_LEGACY_CONTROL_PORT: True,
    }


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Stub out setup function."""
    with patch(
        "homeassistant.components.sky_remote.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
