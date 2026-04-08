"""Tests for Vizio init."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.components.vizio import DATA_APPS
from homeassistant.components.vizio.const import DOMAIN
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    APP_LIST,
    HOST2,
    MOCK_SPEAKER_CONFIG,
    MOCK_USER_VALID_TV_CONFIG,
    MODEL,
    NAME2,
    UNIQUE_ID,
    VERSION,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_tv_load_and_unload(hass: HomeAssistant) -> None:
    """Test loading and unloading TV entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(Platform.MEDIA_PLAYER)) == 1
    assert DATA_APPS in hass.data

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    entities = hass.states.async_entity_ids(Platform.MEDIA_PLAYER)
    assert len(entities) == 1
    for entity in entities:
        assert hass.states.get(entity).state == STATE_UNAVAILABLE
    assert DATA_APPS not in hass.data


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_speaker_load_and_unload(hass: HomeAssistant) -> None:
    """Test loading and unloading speaker entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SPEAKER_CONFIG, unique_id=UNIQUE_ID
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(Platform.MEDIA_PLAYER)) == 1

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    entities = hass.states.async_entity_ids(Platform.MEDIA_PLAYER)
    assert len(entities) == 1
    for entity in entities:
        assert hass.states.get(entity).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures(
    "vizio_connect", "vizio_bypass_update", "vizio_data_coordinator_update_failure"
)
async def test_coordinator_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator update failure after 10 days."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(Platform.MEDIA_PLAYER)) == 1
    assert DATA_APPS in hass.data

    # Failing 25 days in a row should result in a single log message
    # (first one after 10 days, next one would be at 30 days)
    for days in range(1, 25):
        freezer.tick(timedelta(days=days))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    err_msg = "Unable to retrieve the apps list from the external server"
    assert len([record for record in caplog.records if err_msg in record.msg]) == 1


@pytest.mark.usefixtures("vizio_connect", "vizio_bypass_update")
async def test_apps_coordinator_persists_until_last_tv_unloads(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test shared apps coordinator is not shut down until the last TV entry unloads."""
    config_entry_1 = MockConfigEntry(
        domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
    )
    config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: NAME2,
            CONF_HOST: HOST2,
            CONF_DEVICE_CLASS: MediaPlayerDeviceClass.TV,
            CONF_ACCESS_TOKEN: "deadbeef2",
        },
        unique_id="testid2",
    )
    config_entry_1.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_1.entry_id)
    await hass.async_block_till_done()

    config_entry_2.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_2.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(Platform.MEDIA_PLAYER)) == 2

    # Unload first TV — coordinator should still be fetching apps
    assert await hass.config_entries.async_unload(config_entry_1.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.vizio.coordinator.gen_apps_list_from_url",
        return_value=APP_LIST,
    ) as mock_fetch:
        freezer.tick(timedelta(days=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_fetch.call_count == 1

    # Unload second (last) TV — coordinator should stop fetching apps
    assert await hass.config_entries.async_unload(config_entry_2.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.vizio.coordinator.gen_apps_list_from_url",
        return_value=APP_LIST,
    ) as mock_fetch:
        freezer.tick(timedelta(days=2))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_fetch.call_count == 0


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_device_registry_model_and_version(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that coordinator populates device registry with model and version."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, UNIQUE_ID)})
    assert device is not None
    assert device.model == MODEL
    assert device.sw_version == VERSION
    assert device.manufacturer == "VIZIO"


@pytest.mark.usefixtures("vizio_connect", "vizio_bypass_update")
async def test_device_registry_without_model_or_version(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test device registry when model and version are unavailable."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, UNIQUE_ID)})
    assert device is not None
    assert device.model is None
    assert device.sw_version is None
    assert device.manufacturer == "VIZIO"
