"""Tests for Vizio init."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from vizaio import VizioConnectionError, VizioNotFoundError

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerDeviceClass,
)
from homeassistant.components.vizio import DATA_APPS
from homeassistant.components.vizio.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import get_mock_inputs, setup_integration
from .const import (
    APP_RECORDS,
    CURRENT_INPUT,
    ENTITY_ID,
    HOST2,
    INPUT_LIST,
    MODEL,
    NAME2,
    UNIQUE_ID,
    VERSION,
    audio_setting,
    state_extended,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_tv_load_and_unload(
    hass: HomeAssistant, mock_tv_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading TV entry."""
    await setup_integration(hass, mock_tv_config_entry)
    assert len(hass.states.async_entity_ids(MEDIA_PLAYER_DOMAIN)) == 1
    assert DATA_APPS in hass.data

    assert await hass.config_entries.async_unload(mock_tv_config_entry.entry_id)
    await hass.async_block_till_done()
    entities = hass.states.async_entity_ids(MEDIA_PLAYER_DOMAIN)
    assert len(entities) == 1
    for entity in entities:
        assert hass.states.get(entity).state == STATE_UNAVAILABLE
    assert DATA_APPS not in hass.data


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_speaker_load_and_unload(
    hass: HomeAssistant, mock_speaker_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading speaker entry."""
    await setup_integration(hass, mock_speaker_config_entry)
    assert len(hass.states.async_entity_ids(MEDIA_PLAYER_DOMAIN)) == 1

    assert await hass.config_entries.async_unload(mock_speaker_config_entry.entry_id)
    await hass.async_block_till_done()
    entities = hass.states.async_entity_ids(MEDIA_PLAYER_DOMAIN)
    assert len(entities) == 1
    for entity in entities:
        assert hass.states.get(entity).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures(
    "vizio_connect", "vizio_bypass_update", "vizio_data_coordinator_update_failure"
)
async def test_coordinator_update_failure(
    hass: HomeAssistant,
    mock_tv_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator update failure after 10 days."""
    await setup_integration(hass, mock_tv_config_entry)
    assert len(hass.states.async_entity_ids(MEDIA_PLAYER_DOMAIN)) == 1
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
    hass: HomeAssistant,
    mock_tv_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test shared apps coordinator is not shut down until the last TV entry unloads."""
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
    await setup_integration(hass, mock_tv_config_entry)

    config_entry_2.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_2.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(MEDIA_PLAYER_DOMAIN)) == 2

    # Unload first TV — coordinator should still be fetching apps
    assert await hass.config_entries.async_unload(mock_tv_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.vizio.coordinator.fetch_remote_app_catalog",
        return_value=APP_RECORDS,
    ) as mock_fetch:
        freezer.tick(timedelta(days=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_fetch.call_count == 1

    # Unload second (last) TV — coordinator should stop fetching apps
    assert await hass.config_entries.async_unload(config_entry_2.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.vizio.coordinator.fetch_remote_app_catalog",
        return_value=APP_RECORDS,
    ) as mock_fetch:
        freezer.tick(timedelta(days=2))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_fetch.call_count == 0


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_device_registry_model_and_version(
    hass: HomeAssistant,
    mock_tv_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that coordinator populates device registry with model and version."""
    await setup_integration(hass, mock_tv_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, UNIQUE_ID)})
    assert device is not None
    assert device.model == MODEL
    assert device.sw_version == VERSION
    assert device.manufacturer == "VIZIO"


@pytest.mark.usefixtures("vizio_connect", "vizio_bypass_update")
async def test_device_registry_without_model_or_version(
    hass: HomeAssistant,
    mock_tv_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry when model and version are unavailable."""
    await setup_integration(hass, mock_tv_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, UNIQUE_ID)})
    assert device is not None
    assert device.model is None
    assert device.sw_version is None
    assert device.manufacturer == "VIZIO"


@pytest.mark.usefixtures("vizio_connect")
async def test_state_extended_polling(
    hass: HomeAssistant, mock_tv_config_entry: MockConfigEntry
) -> None:
    """Test modern firmware polls via a single state_extended call."""
    with (
        patch(
            "homeassistant.components.vizio.Vizio.get_state_extended",
            return_value=state_extended(current_input=CURRENT_INPUT),
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_settings",
            return_value={"volume": audio_setting("volume", 50)},
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_inputs",
            return_value=get_mock_inputs(INPUT_LIST),
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_model_name",
            return_value=MODEL,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_version",
            return_value=VERSION,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_power_state"
        ) as mock_power_state,
        patch(
            "homeassistant.components.vizio.Vizio.get_current_input"
        ) as mock_current_input,
        patch(
            "homeassistant.components.vizio.Vizio.get_current_app_config"
        ) as mock_app_config,
    ):
        await setup_integration(hass, mock_tv_config_entry)

        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_ON
        assert state.attributes["source"] == CURRENT_INPUT
        # The bundled endpoint replaces the individual state getters
        mock_power_state.assert_not_called()
        mock_current_input.assert_not_called()
        mock_app_config.assert_not_called()


@pytest.mark.usefixtures("vizio_connect")
async def test_state_extended_power_off(
    hass: HomeAssistant, mock_tv_config_entry: MockConfigEntry
) -> None:
    """Test state_extended reporting the device as off."""
    with (
        patch(
            "homeassistant.components.vizio.Vizio.get_state_extended",
            return_value=state_extended(power_on=False),
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_model_name",
            return_value=MODEL,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_version",
            return_value=VERSION,
        ),
        patch("homeassistant.components.vizio.Vizio.get_settings") as mock_settings,
    ):
        await setup_integration(hass, mock_tv_config_entry)

        assert hass.states.get(ENTITY_ID).state == STATE_OFF
        mock_settings.assert_not_called()


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_state_extended_probed_only_once(
    hass: HomeAssistant,
    mock_tv_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test firmware without state_extended is not re-probed every refresh."""
    await setup_integration(hass, mock_tv_config_entry)

    with patch(
        "homeassistant.components.vizio.Vizio.get_state_extended",
        side_effect=VizioNotFoundError("not supported"),
    ) as mock_state_extended:
        for _ in range(3):
            freezer.tick(timedelta(minutes=1))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()

        mock_state_extended.assert_not_called()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("vizio_connect")
async def test_state_extended_connection_error(
    hass: HomeAssistant, mock_tv_config_entry: MockConfigEntry
) -> None:
    """Test a state_extended connection error fails the update."""
    with (
        patch(
            "homeassistant.components.vizio.Vizio.get_state_extended",
            side_effect=VizioConnectionError("cannot connect"),
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_model_name",
            return_value=MODEL,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_version",
            return_value=VERSION,
        ),
    ):
        mock_tv_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_tv_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_tv_config_entry.state is ConfigEntryState.SETUP_RETRY
