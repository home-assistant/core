"""Test fixtures for Tasmota component."""

from unittest.mock import AsyncMock, patch

from aiogithubapi import GitHubReleaseModel
from hatasmota.discovery import get_status_sensor_entities
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.tasmota.const import (
    CONF_DISCOVERY_PREFIX,
    DEFAULT_PREFIX,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from .test_common import NEWER_VERSION

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
                "tag_name": f"v{NEWER_VERSION}",
                "name": f"Tasmota {NEWER_VERSION}",
                "html_url": f"https://github.com/arendst/Tasmota/releases/tag/v{NEWER_VERSION}",
                "body": "",
            }
        )
    )

    with patch(
        "aiogithubapi.namespaces.releases.GitHubReleasesNamespace.latest",
        new=AsyncMock(return_value=mock_response),
    ):
        yield


@pytest.fixture
def update_entity_mqtt_disabled() -> bool:
    """Fixture to allow enabling MQTT for the firmware update entity."""
    return True


@pytest.fixture(autouse=True)
def disable_update_entity_mqtt(update_entity_mqtt_disabled: bool):
    """Keep the firmware update entity off MQTT.

    Its subscriptions and STATUS2 polls would disturb tests of other platforms.
    """
    if not update_entity_mqtt_disabled:
        yield
        return
    with patch("hatasmota.update.TasmotaUpdate.subscribe_topics"):
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
