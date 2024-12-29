"""Common fixtures for the Happiest Baby Snoo tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from .mock_data import MOCK_AMAZON_AUTH, MOCK_SNOO_AUTH


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.snoo.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="mock_amazon_auth")
def mock_amazon_auth() -> None:
    """Return a fake response for authing to amazon."""


@pytest.fixture(name="bypass_api")
def bypass_api(mock_snoo_auth, mock_amazon_auth, mock_reauth) -> None:
    """Bypass the Snoo api."""
    with (
        patch(
            "homeassistant.components.snoo.config_flow.Snoo.auth_snoo",
            return_value=MOCK_SNOO_AUTH,
        ),
        patch(
            "homeassistant.components.snoo.Snoo.auth_snoo",
            return_value=MOCK_SNOO_AUTH,
        ),
        patch(
            "homeassistant.components.snoo.config_flow.Snoo.auth_amazon",
            return_value=MOCK_AMAZON_AUTH,
        ),
        patch(
            "homeassistant.components.snoo.Snoo.auth_amazon",
            return_value=MOCK_AMAZON_AUTH,
        ),
        patch(
            "homeassistant.components.snoo.config_flow.Snoo.schedule_reauthorization",
        ),
        patch(
            "homeassistant.components.snoo.Snoo.schedule_reauthorization",
        ),
    ):
        yield
