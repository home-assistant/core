"""Test fixtures for Slide local."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.slide_local.const import CONF_INVERT_POSITION, DOMAIN
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_MAC

from .const import HOST, SLIDE_INFO_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="slide",
        data={
            CONF_HOST: HOST,
            CONF_API_VERSION: 2,
            CONF_MAC: "12:34:56:78:90:ab",
        },
        options={
            CONF_INVERT_POSITION: False,
        },
        minor_version=1,
        unique_id="12:34:56:78:90:ab",
        entry_id="ce5f5431554d101905d31797e1232da8",
    )


@pytest.fixture
def mock_slide_api() -> Generator[AsyncMock]:
    """Build a fixture for the SlideLocalApi that connects successfully and returns one device."""

    with (
        patch(
            "homeassistant.components.slide_local.coordinator.SlideLocalApi",
            autospec=True,
        ) as mock_slide_local_api,
        patch(
            "homeassistant.components.slide_local.config_flow.SlideLocalApi",
            new=mock_slide_local_api,
        ),
    ):
        client = mock_slide_local_api.return_value
        client.slide_info.return_value = SLIDE_INFO_DATA
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.slide_local.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
