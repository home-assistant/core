"""Test configuration for PS4."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.pjlink.const import CONF_ENCODING, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_connection_create() -> AsyncMock:
    """Return the default mocked connection.create."""
    proj = AsyncMock()
    with patch(
        # "pjlink.Connection.create",
        "pypjlink.Projector.from_address",
        return_value=proj,
    ) as mock:
        yield mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 4352,
            CONF_NAME: "New PJLink Projector",
            CONF_ENCODING: "utf-8",
            CONF_PASSWORD: "password",
        },
        options={
            "entity_id": "media_player.new_pjlink_projector",
        },
        unique_id="pjlink-unique-id",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the PJLink integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pjlink.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


# 192.168.2.194
