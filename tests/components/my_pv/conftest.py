"""Common fixtures for the my-PV tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.my_pv.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the my-PV mocked config entry for local devices."""
    return MockConfigEntry(
        title="my-PV AC ELWA 2 0000000000",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "test-password",
        },
        unique_id="1601500000000000",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent running the real integration setup during tests."""
    with patch(
        "homeassistant.components.my_pv.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
