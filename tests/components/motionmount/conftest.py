"""Fixtures for Vogel's MotionMount integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.motionmount.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from . import HOST, PORT, ZEROCONF_MAC, ZEROCONF_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=ZEROCONF_NAME,
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=ZEROCONF_MAC,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.motionmount.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_motionmount_config_flow() -> Generator[None, MagicMock, None]:
    """Return a mocked MotionMount config flow."""

    with patch(
        "homeassistant.components.motionmount.config_flow.motionmount.MotionMount",
        autospec=True,
    ) as motionmount_mock:
        client = motionmount_mock.return_value
        yield client
