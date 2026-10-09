"""Tests for the Genius Hub component."""

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientResponseError

from homeassistant.components.geniushub import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MAC, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_cloud_unique_id_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_geniushub_cloud: AsyncMock,
) -> None:
    """Test that the cloud unique ID is migrated to the entry_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Genius hub",
        data={
            CONF_TOKEN: "abcdef",
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
        },
        entry_id="1234",
    )
    entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN, DOMAIN, "aa:bb:cc:dd:ee:ff_device_78", config_entry=entry
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.geniushub_aa_bb_cc_dd_ee_ff_device_78")
    entity_entry = entity_registry.async_get(
        "sensor.geniushub_aa_bb_cc_dd_ee_ff_device_78"
    )
    assert entity_entry.unique_id == "1234_device_78"


async def test_setup_client_response_error(
    hass: HomeAssistant,
    mock_geniushub_cloud: AsyncMock,
    mock_cloud_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when the hub responds with an error."""
    mock_geniushub_cloud.update.side_effect = ClientResponseError(
        MagicMock(real_url="https://hub"), (), status=401, message="Unauthorized"
    )
    mock_cloud_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_cloud_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_cloud_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_cloud_config_entry.reason == "Setup failed, check your configuration"
