"""Tests for Vizio init."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from vizaio import (
    ChargingStatus,
    DeviceType,
    VizioAuthError,
    VizioConnectionError,
    VizioNotFoundError,
)

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerDeviceClass,
)
from homeassistant.components.vizio import DATA_APPS
from homeassistant.components.vizio.const import (
    CONF_ADDITIONAL_CONFIGS,
    CONF_APPS,
    CONF_DEVICE_TYPE,
    CONF_VOLUME_STEP,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import setup_integration
from .const import (
    ADDITIONAL_APP_CONFIG,
    APP_RECORDS,
    CURRENT_APP,
    CURRENT_INPUT,
    ENTITY_ID,
    HOST,
    HOST2,
    MOCK_USER_VALID_TV_CONFIG,
    MODEL,
    NAME2,
    PORTLESS_HOST,
    UNIQUE_ID,
    VERSION,
    VOLUME_STEP,
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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, UNIQUE_ID), mock_tv_config_entry.entry_id
    )
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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, UNIQUE_ID), mock_tv_config_entry.entry_id
    )
    assert device is not None
    assert device.model is None
    assert device.sw_version is None
    assert device.manufacturer == "VIZIO"


@pytest.mark.usefixtures("vizio_connect")
async def test_state_extended_polling(
    hass: HomeAssistant,
    mock_tv_config_entry: MockConfigEntry,
    mock_vizio: AsyncMock,
) -> None:
    """Test modern firmware polls via a single state_extended call."""
    await setup_integration(hass, mock_tv_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes["source"] == CURRENT_INPUT
    # The bundled endpoint replaces the individual state getters
    mock_vizio.get_power_state.assert_not_called()
    mock_vizio.get_current_input.assert_not_called()
    mock_vizio.get_current_app_config.assert_not_called()


@pytest.mark.usefixtures("vizio_connect")
async def test_state_extended_power_off(
    hass: HomeAssistant,
    mock_tv_config_entry: MockConfigEntry,
    mock_vizio: AsyncMock,
) -> None:
    """Test state_extended reporting the device as off."""
    mock_vizio.get_state_extended.return_value = state_extended(power_on=False)

    await setup_integration(hass, mock_tv_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    mock_vizio.get_settings.assert_not_called()


@pytest.mark.usefixtures("vizio_connect")
async def test_state_extended_probed_only_once(
    hass: HomeAssistant,
    mock_tv_config_entry: MockConfigEntry,
    mock_vizio: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test firmware without state_extended is not re-probed every refresh."""
    mock_vizio.get_state_extended.side_effect = VizioNotFoundError("not supported")

    await setup_integration(hass, mock_tv_config_entry)
    mock_vizio.get_state_extended.reset_mock()

    for _ in range(3):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    mock_vizio.get_state_extended.assert_not_called()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("vizio_connect")
async def test_state_extended_connection_error(
    hass: HomeAssistant,
    mock_tv_config_entry: MockConfigEntry,
    mock_vizio: AsyncMock,
) -> None:
    """Test a state_extended connection error fails the update."""
    mock_vizio.get_state_extended.side_effect = VizioConnectionError("cannot connect")

    mock_tv_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_tv_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_tv_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("vizio_connect", "vizio_bypass_update")
async def test_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    mock_tv_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an auth failure during refresh starts a reauth flow."""
    await setup_integration(hass, mock_tv_config_entry)
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    with patch(
        "homeassistant.components.vizio.Vizio.get_power_state",
        side_effect=VizioAuthError("token rejected"),
    ):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


@pytest.mark.usefixtures("vizio_connect")
async def test_auth_failure_at_setup_triggers_reauth(
    hass: HomeAssistant, mock_tv_config_entry: MockConfigEntry
) -> None:
    """Test an auth failure during setup puts the entry in an error state."""
    with (
        patch(
            "homeassistant.components.vizio.Vizio.get_state_extended",
            side_effect=VizioAuthError("token rejected"),
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_power_state",
            side_effect=VizioAuthError("token rejected"),
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

    assert mock_tv_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_speaker_classified_as_crave(
    hass: HomeAssistant, mock_speaker_config_entry: MockConfigEntry
) -> None:
    """Test a speaker entry is classified once and the result persisted."""
    with (
        patch(
            "homeassistant.components.vizio.async_classify_device",
            return_value=DeviceType.CRAVE360,
        ) as mock_classify,
        patch(
            "homeassistant.components.vizio.Vizio.get_battery_level",
            return_value=80,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_charging_status",
            return_value=ChargingStatus.CHARGING,
        ),
    ):
        await setup_integration(hass, mock_speaker_config_entry)

    mock_classify.assert_called_once()
    assert mock_speaker_config_entry.data[CONF_DEVICE_TYPE] == "crave360"
    assert hass.states.get("sensor.vizio_battery").state == "80"

    # Reload: the persisted device type is used without re-classifying
    with (
        patch(
            "homeassistant.components.vizio.async_classify_device",
        ) as mock_classify,
        patch(
            "homeassistant.components.vizio.Vizio.get_battery_level",
            return_value=80,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_charging_status",
            return_value=ChargingStatus.CHARGING,
        ),
    ):
        assert await hass.config_entries.async_reload(
            mock_speaker_config_entry.entry_id
        )
        await hass.async_block_till_done()
    mock_classify.assert_not_called()


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_speaker_classification_unavailable(
    hass: HomeAssistant, mock_speaker_config_entry: MockConfigEntry
) -> None:
    """Test classification failure falls back to the soundbar profile."""
    # The autouse vizio_no_classification fixture raises VizioConnectionError
    await setup_integration(hass, mock_speaker_config_entry)

    assert CONF_DEVICE_TYPE not in mock_speaker_config_entry.data
    assert hass.states.get("sensor.vizio_battery") is None


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_speaker_classified_as_tv_not_persisted(
    hass: HomeAssistant, mock_speaker_config_entry: MockConfigEntry
) -> None:
    """Test a TV classification result is ignored for a speaker entry."""
    with patch(
        "homeassistant.components.vizio.async_classify_device",
        return_value=DeviceType.TV,
    ):
        await setup_integration(hass, mock_speaker_config_entry)

    assert CONF_DEVICE_TYPE not in mock_speaker_config_entry.data


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_tv_not_classified(
    hass: HomeAssistant, mock_tv_config_entry: MockConfigEntry
) -> None:
    """Test TV entries never trigger device classification."""
    with patch(
        "homeassistant.components.vizio.async_classify_device",
    ) as mock_classify:
        await setup_integration(hass, mock_tv_config_entry)

    mock_classify.assert_not_called()


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_portless_host_is_resolved_and_persisted(hass: HomeAssistant) -> None:
    """Test a config entry storing a host without a port is repaired on setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_USER_VALID_TV_CONFIG, CONF_HOST: PORTLESS_HOST},
        unique_id=UNIQUE_ID,
    )
    with patch(
        "homeassistant.components.vizio.async_resolve_host",
        AsyncMock(return_value=HOST),
    ) as mock_resolve:
        await setup_integration(hass, entry)

    assert mock_resolve.call_args[0][0] == PORTLESS_HOST
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_HOST] == HOST


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_portless_host_resolve_failure_retries(hass: HomeAssistant) -> None:
    """Test setup is retried when the port cannot be determined."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_USER_VALID_TV_CONFIG, CONF_HOST: PORTLESS_HOST},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.vizio.async_resolve_host",
        AsyncMock(side_effect=VizioConnectionError("no SmartCast API")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.data[CONF_HOST] == PORTLESS_HOST


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_host_with_port_is_left_alone(
    hass: HomeAssistant, mock_tv_config_entry: MockConfigEntry
) -> None:
    """Test a host that already has a port is not rewritten.

    async_resolve_host is idempotent, so it is called unconditionally and
    returns the host untouched without any probing of its own.
    """
    await setup_integration(hass, mock_tv_config_entry)

    assert mock_tv_config_entry.data[CONF_HOST] == HOST


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
@pytest.mark.parametrize(
    ("data", "options", "expected_data", "expected_options"),
    [
        pytest.param(
            {
                **MOCK_USER_VALID_TV_CONFIG,
                CONF_VOLUME_STEP: VOLUME_STEP,
                CONF_APPS: {
                    CONF_INCLUDE: [CURRENT_APP],
                    CONF_ADDITIONAL_CONFIGS: [ADDITIONAL_APP_CONFIG],
                },
            },
            {},
            {
                **MOCK_USER_VALID_TV_CONFIG,
                CONF_APPS: {CONF_ADDITIONAL_CONFIGS: [ADDITIONAL_APP_CONFIG]},
            },
            {
                CONF_VOLUME_STEP: VOLUME_STEP,
                CONF_APPS: {CONF_INCLUDE: [CURRENT_APP]},
            },
            id="moves_settings_to_options",
        ),
        pytest.param(
            {**MOCK_USER_VALID_TV_CONFIG, CONF_VOLUME_STEP: VOLUME_STEP},
            {CONF_VOLUME_STEP: VOLUME_STEP + 1},
            MOCK_USER_VALID_TV_CONFIG,
            {CONF_VOLUME_STEP: VOLUME_STEP + 1},
            id="existing_options_win",
        ),
        pytest.param(
            MOCK_USER_VALID_TV_CONFIG,
            {},
            MOCK_USER_VALID_TV_CONFIG,
            {},
            id="nothing_to_migrate",
        ),
    ],
)
async def test_migrate_entry_to_minor_version_2(
    hass: HomeAssistant,
    data: dict[str, Any],
    options: dict[str, Any],
    expected_data: dict[str, Any],
    expected_options: dict[str, Any],
) -> None:
    """Test migrating a 1.1 entry moves settings from data to options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        options=options,
        unique_id=UNIQUE_ID,
        minor_version=1,
    )
    await setup_integration(hass, config_entry)

    assert config_entry.version == 1
    assert config_entry.minor_version == 2
    assert dict(config_entry.data) == expected_data
    assert dict(config_entry.options) == expected_options
