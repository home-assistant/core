"""Test for Roborock init."""
from dataclasses import asdict
from unittest.mock import patch

from roborock.exceptions import RoborockException

from homeassistant.components.roborock import CachedCoordinatorInformation
from homeassistant.components.roborock.const import (
    CONF_BASE_URL,
    CONF_CACHED_INFORMATION,
    CONF_USER_DATA,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component

from .mock_data import BASE_URL, NETWORK_INFO, PROP, USER_DATA, USER_EMAIL

from tests.common import MockConfigEntry


async def test_unload_entry(
    hass: HomeAssistant, bypass_api_fixture, setup_entry: MockConfigEntry
) -> None:
    """Test unloading roboorck integration."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert setup_entry.state is ConfigEntryState.LOADED
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.async_disconnect"
    ) as mock_disconnect:
        assert await hass.config_entries.async_unload(setup_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_disconnect.call_count == 2
        assert setup_entry.state is ConfigEntryState.NOT_LOADED
        assert not hass.data.get(DOMAIN)


async def test_config_entry_not_ready(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test that when coordinator update fails, entry retries."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data",
    ), patch(
        "homeassistant.components.roborock.RoborockDataUpdateCoordinator._async_update_data",
        side_effect=UpdateFailed(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_not_ready_home_data(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test that when we fail to get home data, entry retries."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data",
        side_effect=RoborockException(),
    ), patch(
        "homeassistant.components.roborock.RoborockDataUpdateCoordinator._async_update_data",
        side_effect=UpdateFailed(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_networking_fails_no_cache(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry, bypass_api_fixture
) -> None:
    """Test that when we have no devices cached, and networking fails, we attempt to retry."""
    with patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_networking_fails_one_cache(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry, bypass_api_fixture
) -> None:
    """Test that if networking fails for both devices - but we have one cached, we setup the one that is cached."""
    mock_roborock_entry.data[CONF_CACHED_INFORMATION]["abc123"] = asdict(
        CachedCoordinatorInformation(
            network_info=NETWORK_INFO, supported_entities=set()
        )
    )
    with patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.LOADED


async def test_get_networking_fails_both_cached(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry, bypass_api_fixture
) -> None:
    """Test that if networking fails for both devices, but we have them cached, we still setup."""
    mock_roborock_entry.data[CONF_CACHED_INFORMATION]["abc123"] = asdict(
        CachedCoordinatorInformation(
            network_info=NETWORK_INFO, supported_entities=set()
        )
    )
    mock_roborock_entry.data[CONF_CACHED_INFORMATION]["device_2"] = asdict(
        CachedCoordinatorInformation(
            network_info=NETWORK_INFO, supported_entities=set()
        )
    )

    with patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.LOADED


async def test_get_networking_fails_both_cached_connection_fails_for_one(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry, bypass_api_fixture
) -> None:
    """Test that if networking fails, and one device doesn't get pros, still setup."""
    mock_roborock_entry.data[CONF_CACHED_INFORMATION]["abc123"] = asdict(
        CachedCoordinatorInformation(
            network_info=NETWORK_INFO, supported_entities=set()
        )
    )
    mock_roborock_entry.data[CONF_CACHED_INFORMATION]["device_2"] = asdict(
        CachedCoordinatorInformation(
            network_info=NETWORK_INFO, supported_entities=set()
        )
    )

    with patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        side_effect=RoborockException(),
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.get_prop",
        side_effect=[RoborockException(), PROP],
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.LOADED


async def test_migrate_entry(hass: HomeAssistant, bypass_api_fixture):
    """Test migrating entry from v1 to v2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=USER_EMAIL,
        data={
            CONF_USERNAME: USER_EMAIL,
            CONF_USER_DATA: USER_DATA.as_dict(),
            CONF_BASE_URL: BASE_URL,
        },
        version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
    assert entry.version == 2
    # At this point, the cached information will be loaded - so we cannot assert on its actual value.
    assert CONF_CACHED_INFORMATION in entry.data
