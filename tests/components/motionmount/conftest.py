"""Fixtures for Vogel's MotionMount integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.motionmount.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT

from . import HOST, MAC, PORT, ZEROCONF_MAC, ZEROCONF_NAME

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
def mock_config_entry_with_pin() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=ZEROCONF_NAME,
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_PIN: 1234},
        unique_id=ZEROCONF_MAC,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.motionmount.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_motionmount() -> Generator[MagicMock]:
    """Return a mocked MotionMount config flow."""

    with patch(
        "homeassistant.components.motionmount.motionmount.MotionMount",
        autospec=True,
    ) as motionmount_mock:
        client = motionmount_mock.return_value
        client.name = ZEROCONF_NAME
        client.mac = MAC
        yield client
