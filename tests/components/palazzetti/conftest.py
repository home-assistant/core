"""Fixtures for Palazzetti integration tests."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.palazzetti.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="palazzetti",
        domain=DOMAIN,
        data={CONF_NAME: "name", CONF_HOST: "example", CONF_MAC: "mac"},
        unique_id="unique_id",
    )


@pytest.fixture
def mock_palazzetti():
    """Return a mocked PalazzettiClient."""
    with (
        patch(
            "homeassistant.components.palazzetti.coordinator.PalazzettiClient",
            AsyncMock,
        ) as client,
    ):
        client.connect = AsyncMock(return_value=True)
        client.update_state = AsyncMock(return_value=True)
        client.mac = AsyncMock(return_value="11:22:33:44:55:66")
        client.name = AsyncMock(return_value="Stove")
        yield client
