"""Common fixtures for the victron_gx tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from victron_mqtt import Hub as VictronVenusHub
from victron_mqtt.testing import create_mocked_hub

from homeassistant.components.victron_gx import PLATFORMS
from homeassistant.components.victron_gx.const import (
    CONF_INSTALLATION_ID,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import MOCK_HOST, MOCK_INSTALLATION_ID, MOCK_MODEL, MOCK_SERIAL

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.victron_gx.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: 1883,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_pass",
            CONF_SSL: False,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_MODEL: MOCK_MODEL,
            CONF_SERIAL: MOCK_SERIAL,
        },
        title=f"Victron OS {MOCK_INSTALLATION_ID} ({MOCK_HOST}:1883)",
    )


async def _async_init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> tuple[VictronVenusHub, MockConfigEntry]:
    """Set up the Victron GX MQTT integration for testing."""
    mock_config_entry.add_to_hass(hass)

    victron_hub = await create_mocked_hub()

    with (
        patch("homeassistant.components.victron_gx.PLATFORMS", platforms),
        patch(
            "homeassistant.components.victron_gx.hub.VictronVenusHub"
        ) as mock_hub_class,
    ):
        mock_hub_class.return_value = victron_hub

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return victron_hub, mock_config_entry


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> tuple[VictronVenusHub, MockConfigEntry]:
    """Set up the Victron GX metric platforms for testing."""
    return await _async_init_integration(
        hass,
        mock_config_entry,
        [platform for platform in PLATFORMS if platform is not Platform.UPDATE],
    )


@pytest.fixture
async def init_integration_with_update(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> tuple[VictronVenusHub, MockConfigEntry]:
    """Set up all Victron GX platforms, including firmware updates."""
    return await _async_init_integration(hass, mock_config_entry, PLATFORMS)
