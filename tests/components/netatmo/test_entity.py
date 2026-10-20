"""Tests for the error handling of Netatmo entity actions."""

from datetime import timedelta
from typing import Any

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pyatmo
from pyatmo.exceptions import ApiTooManyRequestError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.cover import ATTR_POSITION, DOMAIN as COVER_DOMAIN
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.components.netatmo.const import (
    ATTR_CAMERA_LIGHT_MODE,
    ATTR_END_DATETIME,
    ATTR_PERSON,
    ATTR_SCHEDULE_NAME,
    ATTR_TARGET_TEMPERATURE,
    ATTR_TIME_PERIOD,
    DOMAIN,
    SERVICE_CLEAR_TEMPERATURE_SETTING,
    SERVICE_SET_CAMERA_LIGHT,
    SERVICE_SET_PERSON_AWAY,
    SERVICE_SET_PERSONS_HOME,
    SERVICE_SET_PRESET_MODE_WITH_END_DATETIME,
    SERVICE_SET_SCHEDULE,
    SERVICE_SET_TEMPERATURE_WITH_END_DATETIME,
    SERVICE_SET_TEMPERATURE_WITH_TIME_PERIOD,
)
from homeassistant.components.select import ATTR_OPTION, DOMAIN as SELECT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_PERSONS,
    ATTR_TEMPERATURE,
    CONF_WEBHOOK_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SELECT_OPTION,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import (
    FAKE_WEBHOOK_ACTIVATION,
    fail_write_requests,
    selected_platforms,
    simulate_webhook,
)

BUTTON_ENTITY = "button.entrance_blinds_preferred_position"
CAMERA_ENTITY = "camera.hall"
CLIMATE_ENTITY = "climate.livingroom_livingroom"
COVER_ENTITY = "cover.entrance_blinds"
FLOODLIGHT_CAMERA_ENTITY = "camera.front"
FLOODLIGHT_ENTITY = "light.front"
LIGHT_ENTITY = "light.bathroom_light"
SWITCH_ENTITY = "switch.prise"

FLOODLIGHT_ON = {
    "event_type": "light_mode",
    "device_id": "12:34:56:10:b9:0e",
    "camera_id": "12:34:56:10:b9:0e",
    "event_id": "601dce1560abca1ebad9b723",
    "push_type": "NOC-light_mode",
    "sub_type": "on",
}


async def _setup_with_webhook(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Set up all platforms with a delivering webhook.

    The camera floodlight is only available while the webhook delivers.
    """
    with selected_platforms(
        [
            Platform.BUTTON,
            Platform.CAMERA,
            Platform.CLIMATE,
            Platform.COVER,
            Platform.FAN,
            Platform.LIGHT,
            Platform.SELECT,
            Platform.SWITCH,
        ]
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)
    await simulate_webhook(hass, webhook_id, FLOODLIGHT_ON)


@pytest.mark.usefixtures("netatmo_auth")
@pytest.mark.parametrize(
    ("domain", "service", "service_data"),
    [
        pytest.param(
            CAMERA_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: CAMERA_ENTITY},
            id="camera_turn_on",
        ),
        pytest.param(
            CAMERA_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: CAMERA_ENTITY},
            id="camera_turn_off",
        ),
        pytest.param(
            DOMAIN,
            SERVICE_SET_PERSONS_HOME,
            {ATTR_ENTITY_ID: CAMERA_ENTITY, ATTR_PERSONS: "John Doe"},
            id="camera_set_persons_home",
        ),
        pytest.param(
            DOMAIN,
            SERVICE_SET_PERSON_AWAY,
            {ATTR_ENTITY_ID: CAMERA_ENTITY, ATTR_PERSON: "Richard Doe"},
            id="camera_set_person_away",
        ),
        pytest.param(
            DOMAIN,
            SERVICE_SET_CAMERA_LIGHT,
            {ATTR_ENTITY_ID: FLOODLIGHT_CAMERA_ENTITY, ATTR_CAMERA_LIGHT_MODE: "on"},
            id="camera_set_camera_light",
        ),
        pytest.param(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: CLIMATE_ENTITY, ATTR_PRESET_MODE: PRESET_AWAY},
            id="climate_set_preset_mode",
        ),
        pytest.param(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: CLIMATE_ENTITY, ATTR_TEMPERATURE: 21},
            id="climate_set_temperature",
        ),
        pytest.param(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: CLIMATE_ENTITY},
            id="climate_turn_on",
        ),
        pytest.param(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: CLIMATE_ENTITY},
            id="climate_turn_off",
        ),
        pytest.param(
            DOMAIN,
            SERVICE_SET_SCHEDULE,
            {ATTR_ENTITY_ID: CLIMATE_ENTITY, ATTR_SCHEDULE_NAME: "Winter"},
            id="climate_set_schedule",
        ),
        pytest.param(
            DOMAIN,
            SERVICE_SET_PRESET_MODE_WITH_END_DATETIME,
            {
                ATTR_ENTITY_ID: CLIMATE_ENTITY,
                ATTR_PRESET_MODE: PRESET_AWAY,
                ATTR_END_DATETIME: "2030-01-01 12:00:00",
            },
            id="climate_set_preset_mode_with_end_datetime",
        ),
        pytest.param(
            DOMAIN,
            SERVICE_SET_TEMPERATURE_WITH_END_DATETIME,
            {
                ATTR_ENTITY_ID: CLIMATE_ENTITY,
                ATTR_TARGET_TEMPERATURE: 19.5,
                ATTR_END_DATETIME: "2030-01-01 12:00:00",
            },
            id="climate_set_temperature_with_end_datetime",
        ),
        pytest.param(
            DOMAIN,
            SERVICE_SET_TEMPERATURE_WITH_TIME_PERIOD,
            {
                ATTR_ENTITY_ID: CLIMATE_ENTITY,
                ATTR_TARGET_TEMPERATURE: 19.5,
                ATTR_TIME_PERIOD: "02:00:00",
            },
            id="climate_set_temperature_with_time_period",
        ),
        pytest.param(
            DOMAIN,
            SERVICE_CLEAR_TEMPERATURE_SETTING,
            {ATTR_ENTITY_ID: CLIMATE_ENTITY},
            id="climate_clear_temperature_setting",
        ),
        pytest.param(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: COVER_ENTITY},
            id="cover_open",
        ),
        pytest.param(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: COVER_ENTITY},
            id="cover_close",
        ),
        pytest.param(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: COVER_ENTITY},
            id="cover_stop",
        ),
        pytest.param(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: COVER_ENTITY, ATTR_POSITION: 50},
            id="cover_set_position",
        ),
        pytest.param(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "fan.centralized_ventilation_controler",
                ATTR_PRESET_MODE: "fast",
            },
            id="fan_set_preset_mode",
        ),
        pytest.param(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: FLOODLIGHT_ENTITY},
            id="floodlight_turn_on",
        ),
        pytest.param(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: FLOODLIGHT_ENTITY},
            id="floodlight_turn_off",
        ),
        pytest.param(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: LIGHT_ENTITY},
            id="light_turn_on",
        ),
        pytest.param(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: LIGHT_ENTITY, ATTR_BRIGHTNESS: 128},
            id="light_turn_on_brightness",
        ),
        pytest.param(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: LIGHT_ENTITY},
            id="light_turn_off",
        ),
        pytest.param(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.myhome_schedule", ATTR_OPTION: "Winter"},
            id="select_option",
        ),
        pytest.param(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_ENTITY},
            id="switch_turn_on",
        ),
        pytest.param(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: SWITCH_ENTITY},
            id="switch_turn_off",
        ),
    ],
)
async def test_failed_action_raises(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    domain: str,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test a failed Netatmo request raises a translated error and writes no state."""
    await _setup_with_webhook(hass, config_entry)
    entity_id = service_data[ATTR_ENTITY_ID]
    reported = hass.states.get(entity_id).last_reported

    fail_write_requests(hass, config_entry, pyatmo.ApiError("Device unreachable"))
    # Any write after this point gets a newer timestamp
    freezer.tick(timedelta(seconds=1))

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(domain, service, service_data, blocking=True)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "api_error"
    assert exc_info.value.translation_placeholders == {"error": "Device unreachable"}
    # Compared by last_reported: writing an unchanged state keeps the same State
    # object, so comparing states would miss an optimistic write of the old value
    assert hass.states.get(entity_id).last_reported == reported


@pytest.mark.usefixtures("netatmo_auth", "entity_registry_enabled_by_default")
async def test_failed_button_press_raises(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test a failed button press raises a translated error.

    The button records the press time before calling the device, so unlike the
    other actions its state does change.
    """
    await _setup_with_webhook(hass, config_entry)
    fail_write_requests(hass, config_entry, pyatmo.ApiError("Device unreachable"))

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: BUTTON_ENTITY},
            blocking=True,
        )

    assert exc_info.value.translation_key == "api_error"
    assert exc_info.value.translation_placeholders == {"error": "Device unreachable"}


@pytest.mark.usefixtures("netatmo_auth")
@pytest.mark.parametrize(
    ("error", "translation_key", "placeholders"),
    [
        pytest.param(
            pyatmo.ApiThrottlingError("Too many requests"),
            "rate_limited",
            None,
            id="throttled",
        ),
        pytest.param(
            ApiTooManyRequestError("Too many requests"),
            "rate_limited",
            None,
            id="too_many_requests",
        ),
        pytest.param(
            TimeoutError(),
            "api_error",
            {"error": "TimeoutError"},
            id="timeout",
        ),
        pytest.param(
            aiohttp.ClientConnectionError("Connection reset"),
            "api_error",
            {"error": "Connection reset"},
            id="connection_error",
        ),
    ],
)
async def test_failed_action_error_types(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    error: Exception,
    translation_key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Test each kind of request failure maps to its translated error."""
    await _setup_with_webhook(hass, config_entry)
    fail_write_requests(hass, config_entry, error)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_ENTITY},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == placeholders
