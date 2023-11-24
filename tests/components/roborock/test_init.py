"""Test for Roborock init."""
from dataclasses import asdict
from datetime import timedelta
from unittest.mock import patch

from roborock import RoborockException, RoborockInvalidCredentials

from homeassistant.components.roborock.const import (
    CONF_BASE_URL,
    CONF_USER_DATA,
    DOMAIN,
)
from homeassistant.components.roborock.models import CachedCoordinatorInformation
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_USERNAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .mock_data import (
    BASE_URL,
    CACHED_COORD_MAPS,
    NETWORK_INFO,
    PROP,
    USER_DATA,
    USER_EMAIL,
)

from tests.common import MockConfigEntry, async_fire_time_changed


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
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.get_prop",
        side_effect=RoborockException(),
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
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.get_prop",
        side_effect=RoborockException(),
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


async def test_get_networking_fails_none(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry, bypass_api_fixture
) -> None:
    """Test that when networking returns None, we attempt to retry."""
    with patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        return_value=None,
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_cloud_client_fails_props_cached(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture,
    hass_storage,
) -> None:
    """Test that if networking succeeds, but we can't communicate locally with the vacuum, we can't get props, set up."""
    hass_storage[DOMAIN] = {
        "version": 1,
        "data": {
            "abc123": asdict(
                CachedCoordinatorInformation(
                    network_info=NETWORK_INFO,
                    supported_entities={
                        "status_abc123",
                    },
                    map_info=CACHED_COORD_MAPS,
                )
            )
        },
    }
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.ping",
        side_effect=RoborockException(),
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockMqttClient.get_prop",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.LOADED


async def test_local_client_fails_props(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry, bypass_api_fixture
) -> None:
    """Test that if networking succeeds, but we can't communicate locally with the vacuum, we can't get props, fail."""
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.get_prop",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_networking_fails_one_cache(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture,
    hass_storage,
) -> None:
    """Test that if networking fails for both devices - but we have one cached, we setup the one that is cached."""
    hass_storage[DOMAIN] = {
        "version": 1,
        "data": {
            "abc123": asdict(
                CachedCoordinatorInformation(
                    network_info=NETWORK_INFO,
                    supported_entities=set(),
                    map_info=CACHED_COORD_MAPS,
                )
            )
        },
    }
    with patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.LOADED


async def test_get_networking_fails_both_cached(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture,
    hass_storage,
) -> None:
    """Test that if networking fails for both devices, but we have them cached, we still setup."""
    hass_storage[DOMAIN] = {
        "version": 1,
        "data": {
            "abc123": asdict(
                CachedCoordinatorInformation(
                    network_info=NETWORK_INFO,
                    supported_entities=set(),
                    map_info=CACHED_COORD_MAPS,
                )
            ),
            "device_2": asdict(
                CachedCoordinatorInformation(
                    network_info=NETWORK_INFO,
                    supported_entities=set(),
                    map_info=CACHED_COORD_MAPS,
                )
            ),
        },
    }

    with patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.LOADED


async def test_get_networking_fails_both_cached_connection_fails_for_one(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture,
    hass_storage,
) -> None:
    """Test that if networking fails, and one device doesn't get props, still setup."""
    hass_storage[DOMAIN] = {
        "version": 1,
        "data": {
            "abc123": asdict(
                CachedCoordinatorInformation(
                    network_info=NETWORK_INFO,
                    supported_entities={
                        "dnd_start_time_abc123",
                        "dnd_switch_abc123",
                        "volume_abc123",
                    },
                    map_info=CACHED_COORD_MAPS,
                )
            ),
            "device_2": asdict(
                CachedCoordinatorInformation(
                    network_info=NETWORK_INFO,
                    supported_entities=set(),
                    map_info=CACHED_COORD_MAPS,
                )
            ),
        },
    }

    with patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        side_effect=RoborockException(),
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.get_prop",
        side_effect=[RoborockException(), PROP],
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get("time.roborock_s7_maxv_do_not_disturb_begin").state
        == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("switch.roborock_s7_maxv_do_not_disturb").state
        == STATE_UNAVAILABLE
    )
    assert hass.states.get("number.roborock_s7_maxv_volume").state == STATE_UNAVAILABLE


async def test_get_networking_fails_both_cached_connection_fails_for_both(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture,
    hass_storage,
) -> None:
    """Test that if networking fails, and both devices can't get props, setup with both unavailable."""
    hass_storage[DOMAIN] = {
        "version": 1,
        "data": {
            "abc123": asdict(
                CachedCoordinatorInformation(
                    network_info=NETWORK_INFO,
                    supported_entities={
                        "status_abc123",
                    },
                    map_info=CACHED_COORD_MAPS,
                )
            ),
            "device_2": asdict(
                CachedCoordinatorInformation(
                    network_info=NETWORK_INFO,
                    supported_entities=set(),
                    map_info=CACHED_COORD_MAPS,
                )
            ),
        },
    }

    with patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        side_effect=RoborockException(),
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.get_prop",
        side_effect=RoborockException(),
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.get_multi_maps_list",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.LOADED
    assert len(hass.states.async_all("sensor")) == 1
    assert hass.states.get("sensor.roborock_s7_maxv_status").state == STATE_UNAVAILABLE
    # Recover
    future = dt_util.utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.roborock_s7_maxv_status").state == "charging"


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
    assert entry.version == 1


async def test_reauth_started(
    hass: HomeAssistant, bypass_api_fixture, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test reauth flow started."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data",
        side_effect=RoborockInvalidCredentials(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
