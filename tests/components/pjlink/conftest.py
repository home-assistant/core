"""Test configuration for PS4."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.pjlink.const import CONF_ENCODING, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 4352,
            CONF_NAME: "PJLink Projector",
            CONF_ENCODING: "utf-8",
            CONF_PASSWORD: "password",
        },
        unique_id="pjlink-unique-id",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pjlink.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
