"""Tests for Transmission init."""

from unittest.mock import MagicMock, patch

import pytest
from transmission_rpc.error import TransmissionError

from homeassistant.components import transmission
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.transmission.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_CONFIG_DATA

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_api():
    """Mock an api."""
    with patch("transmission_rpc.Client") as api:
        yield api


async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test settings up integration from config entry."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.LOADED


async def test_setup_failed_connection_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test integration failed due to connection error."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    mock_api.side_effect = TransmissionError("111: Connection refused")

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_failed_auth_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test integration failed due to invalid credentials error."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    mock_api.side_effect = TransmissionError("401: Unauthorized")

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data[DOMAIN]


@pytest.mark.parametrize(
    "domain,old_unique_id,key,migration_needed",
    [
        (SENSOR_DOMAIN, "0.0.0.0-Transmission Down Speed", "download", True),
        (SENSOR_DOMAIN, "0.0.0.0-Transmission Up Speed", "upload", True),
        (SENSOR_DOMAIN, "0.0.0.0-Transmission Status", "status", True),
        (
            SENSOR_DOMAIN,
            "0.0.0.0-Transmission Active Torrents",
            "active_torrents",
            True,
        ),
        (
            SENSOR_DOMAIN,
            "0.0.0.0-Transmission Paused Torrents",
            "paused_torrents",
            True,
        ),
        (SENSOR_DOMAIN, "0.0.0.0-Transmission Total Torrents", "total_torrents", True),
        (
            SENSOR_DOMAIN,
            "0.0.0.0-Transmission Completed Torrents",
            "completed_torrents",
            True,
        ),
        (
            SENSOR_DOMAIN,
            "0.0.0.0-Transmission Started Torrents",
            "started_torrents",
            True,
        ),
        (SENSOR_DOMAIN, "0.0.0.0-download", "download", False),
        (SENSOR_DOMAIN, "abcde", "", False),
        (SWITCH_DOMAIN, "0.0.0.0-Transmission Switch", "on_off", True),
        (SWITCH_DOMAIN, "0.0.0.0-Transmission Turtle Mode", "turtle_mode", True),
        (SWITCH_DOMAIN, "0.0.0.0-on_off", "on_off", False),
        (SWITCH_DOMAIN, "abcde", "", False),
    ],
)
async def test_migrate_unique_id(
    hass, domain, old_unique_id: str, key: str, migration_needed: bool
):
    """Test unique id migration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    ent_reg = er.async_get(hass)

    entity: er.RegistryEntry = ent_reg.async_get_or_create(
        suggested_object_id=f"my_{domain}",
        disabled_by=None,
        domain=domain,
        platform=transmission.DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id

    assert await transmission.async_setup_entry(hass, entry) is True

    new_unique_id = f"{entry.entry_id}-{key}" if migration_needed else old_unique_id
    if migration_needed:
        assert (
            ent_reg.async_get_entity_id(domain, transmission.DOMAIN, old_unique_id)
            is None
        )
    assert (
        ent_reg.async_get_entity_id(domain, transmission.DOMAIN, new_unique_id)
        == f"{domain}.my_{domain}"
    )
