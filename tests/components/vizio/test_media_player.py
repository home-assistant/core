"""Tests for Vizio config flow."""
from datetime import timedelta
import logging
from typing import Any, Dict
from unittest.mock import call

from asynctest import patch
import pytest
from pytest import raises
from pyvizio._api.apps import AppConfig
from pyvizio.const import (
    DEVICE_CLASS_SPEAKER as VIZIO_DEVICE_CLASS_SPEAKER,
    DEVICE_CLASS_TV as VIZIO_DEVICE_CLASS_TV,
    INPUT_APPS,
    MAX_VOLUME,
    UNKNOWN_APP,
)
import voluptuous as vol

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DEVICE_CLASS_SPEAKER,
    DEVICE_CLASS_TV,
    DOMAIN as MP_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.components.vizio import validate_apps
from homeassistant.components.vizio.const import (
    CONF_ADDITIONAL_CONFIGS,
    CONF_APPS,
    CONF_VOLUME_STEP,
    DOMAIN,
    VIZIO_SCHEMA,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from .const import (
    ADDITIONAL_APP_CONFIG,
    APP_LIST,
    CURRENT_APP,
    CURRENT_INPUT,
    CUSTOM_APP_NAME,
    CUSTOM_CONFIG,
    ENTITY_ID,
    INPUT_LIST,
    INPUT_LIST_WITH_APPS,
    MOCK_SPEAKER_APPS_FAILURE,
    MOCK_SPEAKER_CONFIG,
    MOCK_TV_APPS_FAILURE,
    MOCK_TV_WITH_ADDITIONAL_APPS_CONFIG,
    MOCK_TV_WITH_EXCLUDE_CONFIG,
    MOCK_TV_WITH_INCLUDE_CONFIG,
    MOCK_USER_VALID_TV_CONFIG,
    NAME,
    UNIQUE_ID,
    VOLUME_STEP,
)

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def _test_setup(
    hass: HomeAssistantType, ha_device_class: str, vizio_power_state: bool
) -> None:
    """Test Vizio Device entity setup."""
    if vizio_power_state:
        ha_power_state = STATE_ON
    elif vizio_power_state is False:
        ha_power_state = STATE_OFF
    else:
        ha_power_state = STATE_UNAVAILABLE

    if ha_device_class == DEVICE_CLASS_SPEAKER:
        vizio_device_class = VIZIO_DEVICE_CLASS_SPEAKER
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=vol.Schema(VIZIO_SCHEMA)(MOCK_SPEAKER_CONFIG),
            unique_id=UNIQUE_ID,
        )
    else:
        vizio_device_class = VIZIO_DEVICE_CLASS_TV
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=vol.Schema(VIZIO_SCHEMA)(MOCK_USER_VALID_TV_CONFIG),
            unique_id=UNIQUE_ID,
        )

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_all_audio_settings",
        return_value={"volume": int(MAX_VOLUME[vizio_device_class] / 2), "mute": "Off"},
    ), patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_power_state",
        return_value=vizio_power_state,
    ), patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_current_app",
    ) as service_call:
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        attr = hass.states.get(ENTITY_ID).attributes
        assert attr["friendly_name"] == NAME
        assert attr["device_class"] == ha_device_class

        assert hass.states.get(ENTITY_ID).state == ha_power_state
        if ha_power_state == STATE_ON:
            assert attr["source_list"] == INPUT_LIST
            assert attr["source"] == CURRENT_INPUT
            if ha_device_class == DEVICE_CLASS_SPEAKER:
                assert not service_call.called
            assert (
                attr["volume_level"]
                == float(int(MAX_VOLUME[vizio_device_class] / 2))
                / MAX_VOLUME[vizio_device_class]
            )


async def _test_setup_with_apps(
    hass: HomeAssistantType, device_config: Dict[str, Any], app: str
) -> None:
    """Test Vizio Device with apps entity setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=vol.Schema(VIZIO_SCHEMA)(device_config), unique_id=UNIQUE_ID
    )

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_all_audio_settings",
        return_value={
            "volume": int(MAX_VOLUME[VIZIO_DEVICE_CLASS_TV] / 2),
            "mute": "Off",
        },
    ), patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_power_state",
        return_value=True,
    ), patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_current_app",
        return_value=app,
    ), patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_current_app_config",
        return_value=AppConfig(**ADDITIONAL_APP_CONFIG["config"]),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        attr = hass.states.get(ENTITY_ID).attributes
        assert attr["friendly_name"] == NAME
        assert attr["device_class"] == DEVICE_CLASS_TV
        assert hass.states.get(ENTITY_ID).state == STATE_ON

        if device_config.get(CONF_APPS, {}).get(CONF_INCLUDE) or device_config.get(
            CONF_APPS, {}
        ).get(CONF_EXCLUDE):
            list_to_test = list(INPUT_LIST_WITH_APPS + [CURRENT_APP])
        elif device_config.get(CONF_APPS, {}).get(CONF_ADDITIONAL_CONFIGS):
            list_to_test = list(
                INPUT_LIST_WITH_APPS
                + APP_LIST
                + [
                    app["name"]
                    for app in device_config[CONF_APPS][CONF_ADDITIONAL_CONFIGS]
                ]
            )
        else:
            list_to_test = list(INPUT_LIST_WITH_APPS + APP_LIST)

        for app_to_remove in INPUT_APPS:
            if app_to_remove in list_to_test:
                list_to_test.remove(app_to_remove)

        assert attr["source_list"] == list_to_test
        assert app in attr["source_list"] or app == UNKNOWN_APP
        if app == UNKNOWN_APP:
            assert attr["source"] == ADDITIONAL_APP_CONFIG["name"]
        else:
            assert attr["source"] == app
        assert (
            attr["volume_level"]
            == float(int(MAX_VOLUME[VIZIO_DEVICE_CLASS_TV] / 2))
            / MAX_VOLUME[VIZIO_DEVICE_CLASS_TV]
        )


async def _test_setup_failure(hass: HomeAssistantType, config: str) -> None:
    """Test generic Vizio entity setup failure."""
    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.can_connect_with_auth_check",
        return_value=False,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=config, unique_id=UNIQUE_ID)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids(MP_DOMAIN)) == 0


async def _test_service(
    hass: HomeAssistantType,
    vizio_func_name: str,
    ha_service_name: str,
    additional_service_data: dict,
    *args,
    **kwargs,
) -> None:
    """Test generic Vizio media player entity service."""
    service_data = {ATTR_ENTITY_ID: ENTITY_ID}
    if additional_service_data:
        service_data.update(additional_service_data)

    with patch(
        f"homeassistant.components.vizio.media_player.VizioAsync.{vizio_func_name}"
    ) as service_call:
        await hass.services.async_call(
            MP_DOMAIN, ha_service_name, service_data=service_data, blocking=True,
        )
        assert service_call.called

        if args or kwargs:
            assert service_call.call_args == call(*args, **kwargs)


async def test_speaker_on(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test Vizio Speaker entity setup when on."""
    await _test_setup(hass, DEVICE_CLASS_SPEAKER, True)


async def test_speaker_off(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test Vizio Speaker entity setup when off."""
    await _test_setup(hass, DEVICE_CLASS_SPEAKER, False)


async def test_speaker_unavailable(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test Vizio Speaker entity setup when unavailable."""
    await _test_setup(hass, DEVICE_CLASS_SPEAKER, None)


async def test_init_tv_on(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test Vizio TV entity setup when on."""
    await _test_setup(hass, DEVICE_CLASS_TV, True)


async def test_init_tv_off(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test Vizio TV entity setup when off."""
    await _test_setup(hass, DEVICE_CLASS_TV, False)


async def test_init_tv_unavailable(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test Vizio TV entity setup when unavailable."""
    await _test_setup(hass, DEVICE_CLASS_TV, None)


async def test_setup_failure_speaker(
    hass: HomeAssistantType, vizio_connect: pytest.fixture
) -> None:
    """Test speaker entity setup failure."""
    await _test_setup_failure(hass, MOCK_SPEAKER_CONFIG)


async def test_setup_failure_tv(
    hass: HomeAssistantType, vizio_connect: pytest.fixture
) -> None:
    """Test TV entity setup failure."""
    await _test_setup_failure(hass, MOCK_USER_VALID_TV_CONFIG)


async def test_services(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test all Vizio media player entity services."""
    await _test_setup(hass, DEVICE_CLASS_TV, True)

    await _test_service(hass, "pow_on", SERVICE_TURN_ON, None)
    await _test_service(hass, "pow_off", SERVICE_TURN_OFF, None)
    await _test_service(
        hass, "mute_on", SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}
    )
    await _test_service(
        hass, "mute_off", SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}
    )
    await _test_service(
        hass, "set_input", SERVICE_SELECT_SOURCE, {ATTR_INPUT_SOURCE: "USB"}, "USB"
    )
    await _test_service(hass, "vol_up", SERVICE_VOLUME_UP, None)
    await _test_service(hass, "vol_down", SERVICE_VOLUME_DOWN, None)
    await _test_service(
        hass, "vol_up", SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 1}
    )
    await _test_service(
        hass, "vol_down", SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0}
    )
    await _test_service(hass, "ch_up", SERVICE_MEDIA_NEXT_TRACK, None)
    await _test_service(hass, "ch_down", SERVICE_MEDIA_PREVIOUS_TRACK, None)


async def test_options_update(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
) -> None:
    """Test when config entry update event fires."""
    await _test_setup(hass, DEVICE_CLASS_SPEAKER, True)
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.options
    new_options = config_entry.options.copy()
    updated_options = {CONF_VOLUME_STEP: VOLUME_STEP}
    new_options.update(updated_options)
    hass.config_entries.async_update_entry(
        entry=config_entry, options=new_options,
    )
    assert config_entry.options == updated_options
    await _test_service(hass, "vol_up", SERVICE_VOLUME_UP, None, num=VOLUME_STEP)


async def _test_update_availability_switch(
    hass: HomeAssistantType,
    initial_power_state: bool,
    final_power_state: bool,
    caplog: pytest.fixture,
) -> None:
    now = dt_util.utcnow()
    future_interval = timedelta(minutes=1)

    # Setup device as if time is right now
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await _test_setup(hass, DEVICE_CLASS_SPEAKER, initial_power_state)

    # Clear captured logs so that only availability state changes are captured for
    # future assertion
    caplog.clear()

    # Fast forward time to future twice to trigger update and assert vizio log message
    for i in range(1, 3):
        future = now + (future_interval * i)
        with patch(
            "homeassistant.components.vizio.media_player.VizioAsync.get_power_state",
            return_value=final_power_state,
        ), patch("homeassistant.util.dt.utcnow", return_value=future), patch(
            "homeassistant.util.utcnow", return_value=future
        ):
            async_fire_time_changed(hass, future)
            await hass.async_block_till_done()
            if final_power_state is None:
                assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
            else:
                assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    # Ensure connection status messages from vizio.media_player appear exactly once
    # (on availability state change)
    vizio_log_list = [
        log
        for log in caplog.records
        if log.name == "homeassistant.components.vizio.media_player"
    ]
    assert len(vizio_log_list) == 1


async def test_update_unavailable_to_available(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
    caplog: pytest.fixture,
) -> None:
    """Test device becomes available after being unavailable."""
    await _test_update_availability_switch(hass, None, True, caplog)


async def test_update_available_to_unavailable(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update: pytest.fixture,
    caplog: pytest.fixture,
) -> None:
    """Test device becomes unavailable after being available."""
    await _test_update_availability_switch(hass, True, None, caplog)


async def test_setup_with_apps(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update_with_apps: pytest.fixture,
    caplog: pytest.fixture,
) -> None:
    """Test device setup with apps."""
    await _test_setup_with_apps(hass, MOCK_USER_VALID_TV_CONFIG, CURRENT_APP)
    await _test_service(
        hass,
        "launch_app",
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: CURRENT_APP},
        CURRENT_APP,
    )


async def test_setup_with_apps_include(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update_with_apps: pytest.fixture,
    caplog: pytest.fixture,
) -> None:
    """Test device setup with apps and apps["include"] in config."""
    await _test_setup_with_apps(hass, MOCK_TV_WITH_INCLUDE_CONFIG, CURRENT_APP)


async def test_setup_with_apps_exclude(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update_with_apps: pytest.fixture,
    caplog: pytest.fixture,
) -> None:
    """Test device setup with apps and apps["exclude"] in config."""
    await _test_setup_with_apps(hass, MOCK_TV_WITH_EXCLUDE_CONFIG, CURRENT_APP)


async def test_setup_with_apps_additional_apps_config(
    hass: HomeAssistantType,
    vizio_connect: pytest.fixture,
    vizio_update_with_apps: pytest.fixture,
    caplog: pytest.fixture,
) -> None:
    """Test device setup with apps and apps["additional_configs"] in config."""
    await _test_setup_with_apps(hass, MOCK_TV_WITH_ADDITIONAL_APPS_CONFIG, UNKNOWN_APP)

    await _test_service(
        hass,
        "launch_app",
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: CURRENT_APP},
        CURRENT_APP,
    )
    await _test_service(
        hass,
        "launch_app_config",
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: CUSTOM_APP_NAME},
        **CUSTOM_CONFIG,
    )

    # Test that invalid app does nothing
    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.launch_app"
    ) as service_call1, patch(
        "homeassistant.components.vizio.media_player.VizioAsync.launch_app_config"
    ) as service_call2:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "_"},
            blocking=True,
        )
        assert not service_call1.called
        assert not service_call2.called


def test_invalid_apps_config(hass: HomeAssistantType):
    """Test that schema validation fails on certain conditions."""
    with raises(vol.Invalid):
        vol.Schema(vol.All(VIZIO_SCHEMA, validate_apps))(MOCK_TV_APPS_FAILURE)

    with raises(vol.Invalid):
        vol.Schema(vol.All(VIZIO_SCHEMA, validate_apps))(MOCK_SPEAKER_APPS_FAILURE)
