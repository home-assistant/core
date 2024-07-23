"""Test helpers."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.fyta.const import CONF_EXPIRATION
from homeassistant.const import CONF_ACCESS_TOKEN

from .test_config_flow import ACCESS_TOKEN, EXPIRATION


@pytest.fixture
def mock_fyta():
    """Build a fixture for the Fyta API that connects successfully and returns one device."""

    mock_fyta_api = AsyncMock()
    with patch(
        "homeassistant.components.fyta.config_flow.FytaConnector",
        return_value=mock_fyta_api,
    ) as mock_fyta_api:
        mock_fyta_api.return_value.login.return_value = {
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_EXPIRATION: EXPIRATION,
        }
        yield mock_fyta_api


@pytest.fixture
def mock_fyta_init():
    """Build a fixture for the Fyta API that connects successfully and returns one device."""

    mock_fyta_api = AsyncMock()
    mock_fyta_api.expiration = datetime.now(tz=UTC) + timedelta(days=1)
    mock_fyta_api.login = AsyncMock(
        return_value={
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_EXPIRATION: EXPIRATION,
        }
    )
    with patch(
        "homeassistant.components.fyta.FytaConnector.__new__",
        return_value=mock_fyta_api,
    ):
        yield mock_fyta_api


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fyta.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
