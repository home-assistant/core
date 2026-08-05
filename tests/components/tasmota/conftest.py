"""Test fixtures for Tasmota component."""

from unittest.mock import AsyncMock, patch

from aiogithubapi import GitHubReleaseModel
from hatasmota.discovery import get_status_sensor_entities
import pytest

from homeassistant.components.tasmota.const import (
    CONF_DISCOVERY_PREFIX,
    DEFAULT_PREFIX,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def disable_debounce():
    """Set MQTT debounce timer to zero."""
    with patch("hatasmota.mqtt.DEBOUNCE_TIMEOUT", 0):
        yield


@pytest.fixture
def status_sensor_disabled():
    """Fixture to allow overriding MQTT config."""
    return True


@pytest.fixture(autouse=True)
def disable_status_sensor(status_sensor_disabled):
    """Disable Tasmota status sensor."""
    wraps = None if status_sensor_disabled else get_status_sensor_entities
    with patch("hatasmota.discovery.get_status_sensor_entities", wraps=wraps):
        yield


@pytest.fixture(autouse=True)
def mock_github_api():
    """Mock the GitHub release API to prevent network requests."""
    mock_response = AsyncMock(
        data=GitHubReleaseModel(
            {
                "tag_name": "v14.6.0",
                "name": "Tasmota 14.6.0",
                "html_url": "https://github.com/arendst/Tasmota/releases/tag/v14.6.0",
                "body": "",
            }
        )
    )

    with patch(
        "aiogithubapi.namespaces.releases.GitHubReleasesNamespace.latest",
        new=AsyncMock(return_value=mock_response),
    ):
        yield


async def setup_tasmota_helper(hass: HomeAssistant) -> None:
    """Set up Tasmota."""
    hass.config.components.add("tasmota")

    entry = MockConfigEntry(
        data={CONF_DISCOVERY_PREFIX: DEFAULT_PREFIX},
        domain=DOMAIN,
        title="Tasmota",
    )

    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "tasmota" in hass.config.components


@pytest.fixture
async def setup_tasmota(hass: HomeAssistant) -> None:
    """Set up Tasmota."""
    await setup_tasmota_helper(hass)
