"""Test helpers."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.slide_local.const import CONF_INVERT_POSITION, DOMAIN
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_PASSWORD

from .const import HOST

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="slide",
        data={
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
            CONF_API_VERSION: 2,
            CONF_INVERT_POSITION: False,
        },
        minor_version=1,
        entry_id="ce5f5431554d101905d31797e1232da8",
    )


@pytest.fixture
def mock_slide_api():
    """Build a fixture for the SlideLocalApi that connects successfully and returns one device."""

    data = load_json_object_fixture("slide_1.json", DOMAIN)

    mock_slide_local_api = AsyncMock()
    mock_slide_local_api.slide_info.return_value = data

    with (
        patch(
            "homeassistant.components.slide_local.SlideLocalApi",
            autospec=True,
            return_value=mock_slide_local_api,
        ),
        patch(
            "homeassistant.components.slide_local.config_flow.SlideLocalApi",
            autospec=True,
            return_value=mock_slide_local_api,
        ),
    ):
        yield mock_slide_local_api


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.slide_local.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
