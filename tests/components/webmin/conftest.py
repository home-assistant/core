"""Fixtures for Webmin integration tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.webmin.const import DEFAULT_PORT
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

TEST_USER_INPUT = {
    CONF_HOST: "192.168.1.1",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_PORT: DEFAULT_PORT,
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.webmin.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
