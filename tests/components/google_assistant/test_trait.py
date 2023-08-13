"""Tests for the Google Assistant traits."""
from datetime import datetime, timedelta
from unittest.mock import ANY, patch

import pytest

from homeassistant.components import (
    alarm_control_panel,
    binary_sensor,
    button,
    camera,
    climate,
    cover,
    fan,
    group,
    humidifier,
    input_boolean,
    input_button,
    input_select,
    light,
    lock,
    media_player,
    scene,
    script,
    select,
    sensor,
    switch,
    vacuum,
)
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.components.camera import CameraEntityFeature
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.fan import FanEntityFeature
from homeassistant.components.google_assistant import const, error, helpers, trait
from homeassistant.components.google_assistant.error import SmartHomeError
from homeassistant.components.humidifier import HumidifierEntityFeature
from homeassistant.components.light import LightEntityFeature
from homeassistant.components.lock import LockEntityFeature
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.components.vacuum import VacuumEntityFeature
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import (
    DOMAIN as HA_DOMAIN,
    EVENT_CALL_SERVICE,
    HomeAssistant,
    State,
)
from homeassistant.util import color

from . import BASIC_CONFIG, MockConfig

from tests.common import async_capture_events, async_mock_service

REQ_ID = "ff36a3cc-ec34-11e6-b1a0-64510650abcf"

BASIC_DATA = helpers.RequestData(
    BASIC_CONFIG, "test-agent", const.SOURCE_CLOUD, REQ_ID, None
)

PIN_CONFIG = MockConfig(secure_devices_pin="1234")

PIN_DATA = helpers.RequestData(
    PIN_CONFIG, "test-agent", const.SOURCE_CLOUD, REQ_ID, None
)


@pytest.mark.parametrize(
    "supported_color_modes", [["brightness"], ["hs"], ["color_temp"]]
)
async def test_brightness_light(hass: HomeAssistant, supported_color_modes) -> None:
    """Test brightness trait support for light domain."""
    assert helpers.get_google_type(light.DOMAIN, None) is not None
    assert trait.BrightnessTrait.supported(
        light.DOMAIN, 0, None, {"supported_color_modes": supported_color_modes}
    )

    trt = trait.BrightnessTrait(
        hass,
        State("light.bla", light.STATE_ON, {light.ATTR_BRIGHTNESS: 243}),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {"brightness": 95}

    events = async_capture_events(hass, EVENT_CALL_SERVICE)

    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await trt.execute(
        trait.COMMAND_BRIGHTNESS_ABSOLUTE, BASIC_DATA, {"brightness": 50}, {}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "light.bla", light.ATTR_BRIGHTNESS_PCT: 50}

    assert len(events) == 1
    assert events[0].data == {
        "domain": "light",
        "service": "turn_on",
        "service_data": {"brightness_pct": 50, "entity_id": "light.bla"},
    }


async def test_camera_stream(hass: HomeAssistant) -> None:
    """Test camera stream trait support for camera domain."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    assert helpers.get_google_type(camera.DOMAIN, None) is not None
    assert trait.CameraStreamTrait.supported(
        camera.DOMAIN, CameraEntityFeature.STREAM, None, None
    )

    trt = trait.CameraStreamTrait(
        hass, State("camera.bla", camera.STATE_IDLE, {}), BASIC_CONFIG
    )

    assert trt.sync_attributes() == {
        "cameraStreamSupportedProtocols": ["hls"],
        "cameraStreamNeedAuthToken": False,
        "cameraStreamNeedDrmEncryption": False,
    }

    assert trt.query_attributes() == {}

    with patch(
        "homeassistant.components.camera.async_request_stream",
        return_value="/api/streams/bla",
    ):
        await trt.execute(trait.COMMAND_GET_CAMERA_STREAM, BASIC_DATA, {}, {})

    assert trt.query_attributes() == {
        "cameraStreamAccessUrl": "https://example.com/api/streams/bla",
        "cameraStreamReceiverAppId": "B45F4572",
    }


async def test_onoff_group(hass: HomeAssistant) -> None:
    """Test OnOff trait support for group domain."""
    assert helpers.get_google_type(group.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(group.DOMAIN, 0, None, None)

    trt_on = trait.OnOffTrait(hass, State("group.bla", STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {"on": True}

    trt_off = trait.OnOffTrait(hass, State("group.bla", STATE_OFF), BASIC_CONFIG)

    assert trt_off.query_attributes() == {"on": False}

    on_calls = async_mock_service(hass, HA_DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: "group.bla"}

    off_calls = async_mock_service(hass, HA_DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: "group.bla"}


async def test_onoff_input_boolean(hass: HomeAssistant) -> None:
    """Test OnOff trait support for input_boolean domain."""
    assert helpers.get_google_type(input_boolean.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(input_boolean.DOMAIN, 0, None, None)

    trt_on = trait.OnOffTrait(hass, State("input_boolean.bla", STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {"on": True}

    trt_off = trait.OnOffTrait(
        hass, State("input_boolean.bla", STATE_OFF), BASIC_CONFIG
    )

    assert trt_off.query_attributes() == {"on": False}

    on_calls = async_mock_service(hass, input_boolean.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: "input_boolean.bla"}

    off_calls = async_mock_service(hass, input_boolean.DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: "input_boolean.bla"}


async def test_onoff_switch(hass: HomeAssistant) -> None:
    """Test OnOff trait support for switch domain."""
    assert helpers.get_google_type(switch.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(switch.DOMAIN, 0, None, None)

    trt_on = trait.OnOffTrait(hass, State("switch.bla", STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {"on": True}

    trt_off = trait.OnOffTrait(hass, State("switch.bla", STATE_OFF), BASIC_CONFIG)

    assert trt_off.query_attributes() == {"on": False}

    trt_assumed = trait.OnOffTrait(
        hass, State("switch.bla", STATE_OFF, {"assumed_state": True}), BASIC_CONFIG
    )
    assert trt_assumed.sync_attributes() == {"commandOnlyOnOff": True}

    on_calls = async_mock_service(hass, switch.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: "switch.bla"}

    off_calls = async_mock_service(hass, switch.DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: "switch.bla"}


async def test_onoff_fan(hass: HomeAssistant) -> None:
    """Test OnOff trait support for fan domain."""
    assert helpers.get_google_type(fan.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(fan.DOMAIN, 0, None, None)

    trt_on = trait.OnOffTrait(hass, State("fan.bla", STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {"on": True}

    trt_off = trait.OnOffTrait(hass, State("fan.bla", STATE_OFF), BASIC_CONFIG)
    assert trt_off.query_attributes() == {"on": False}

    on_calls = async_mock_service(hass, fan.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: "fan.bla"}

    off_calls = async_mock_service(hass, fan.DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: "fan.bla"}


async def test_onoff_light(hass: HomeAssistant) -> None:
    """Test OnOff trait support for light domain."""
    assert helpers.get_google_type(light.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(light.DOMAIN, 0, None, None)

    trt_on = trait.OnOffTrait(hass, State("light.bla", STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {"on": True}

    trt_off = trait.OnOffTrait(hass, State("light.bla", STATE_OFF), BASIC_CONFIG)

    assert trt_off.query_attributes() == {"on": False}

    on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: "light.bla"}

    off_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: "light.bla"}


async def test_onoff_media_player(hass: HomeAssistant) -> None:
    """Test OnOff trait support for media_player domain."""
    assert helpers.get_google_type(media_player.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(media_player.DOMAIN, 0, None, None)

    trt_on = trait.OnOffTrait(hass, State("media_player.bla", STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {"on": True}

    trt_off = trait.OnOffTrait(hass, State("media_player.bla", STATE_OFF), BASIC_CONFIG)

    assert trt_off.query_attributes() == {"on": False}

    on_calls = async_mock_service(hass, media_player.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: "media_player.bla"}

    off_calls = async_mock_service(hass, media_player.DOMAIN, SERVICE_TURN_OFF)

    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: "media_player.bla"}


async def test_onoff_humidifier(hass: HomeAssistant) -> None:
    """Test OnOff trait support for humidifier domain."""
    assert helpers.get_google_type(humidifier.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(humidifier.DOMAIN, 0, None, None)

    trt_on = trait.OnOffTrait(hass, State("humidifier.bla", STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {"on": True}

    trt_off = trait.OnOffTrait(hass, State("humidifier.bla", STATE_OFF), BASIC_CONFIG)

    assert trt_off.query_attributes() == {"on": False}

    on_calls = async_mock_service(hass, humidifier.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: "humidifier.bla"}

    off_calls = async_mock_service(hass, humidifier.DOMAIN, SERVICE_TURN_OFF)

    await trt_on.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: "humidifier.bla"}


async def test_dock_vacuum(hass: HomeAssistant) -> None:
    """Test dock trait support for vacuum domain."""
    assert helpers.get_google_type(vacuum.DOMAIN, None) is not None
    assert trait.DockTrait.supported(vacuum.DOMAIN, 0, None, None)

    trt = trait.DockTrait(hass, State("vacuum.bla", vacuum.STATE_IDLE), BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {"isDocked": False}

    calls = async_mock_service(hass, vacuum.DOMAIN, vacuum.SERVICE_RETURN_TO_BASE)
    await trt.execute(trait.COMMAND_DOCK, BASIC_DATA, {}, {})
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "vacuum.bla"}


async def test_locate_vacuum(hass: HomeAssistant) -> None:
    """Test locate trait support for vacuum domain."""
    assert helpers.get_google_type(vacuum.DOMAIN, None) is not None
    assert trait.LocatorTrait.supported(
        vacuum.DOMAIN, VacuumEntityFeature.LOCATE, None, None
    )

    trt = trait.LocatorTrait(
        hass,
        State(
            "vacuum.bla",
            vacuum.STATE_IDLE,
            {ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.LOCATE},
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {}

    calls = async_mock_service(hass, vacuum.DOMAIN, vacuum.SERVICE_LOCATE)
    await trt.execute(trait.COMMAND_LOCATE, BASIC_DATA, {"silence": False}, {})
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "vacuum.bla"}

    with pytest.raises(helpers.SmartHomeError) as err:
        await trt.execute(trait.COMMAND_LOCATE, BASIC_DATA, {"silence": True}, {})
    assert err.value.code == const.ERR_FUNCTION_NOT_SUPPORTED


async def test_energystorage_vacuum(hass: HomeAssistant) -> None:
    """Test EnergyStorage trait support for vacuum domain."""
    assert helpers.get_google_type(vacuum.DOMAIN, None) is not None
    assert trait.EnergyStorageTrait.supported(
        vacuum.DOMAIN, VacuumEntityFeature.BATTERY, None, None
    )

    trt = trait.EnergyStorageTrait(
        hass,
        State(
            "vacuum.bla",
            vacuum.STATE_DOCKED,
            {
                ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.BATTERY,
                ATTR_BATTERY_LEVEL: 100,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "isRechargeable": True,
        "queryOnlyEnergyStorage": True,
    }

    assert trt.query_attributes() == {
        "descriptiveCapacityRemaining": "FULL",
        "capacityRemaining": [{"rawValue": 100, "unit": "PERCENTAGE"}],
        "capacityUntilFull": [{"rawValue": 0, "unit": "PERCENTAGE"}],
        "isCharging": True,
        "isPluggedIn": True,
    }

    trt = trait.EnergyStorageTrait(
        hass,
        State(
            "vacuum.bla",
            vacuum.STATE_CLEANING,
            {
                ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.BATTERY,
                ATTR_BATTERY_LEVEL: 20,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "isRechargeable": True,
        "queryOnlyEnergyStorage": True,
    }

    assert trt.query_attributes() == {
        "descriptiveCapacityRemaining": "CRITICALLY_LOW",
        "capacityRemaining": [{"rawValue": 20, "unit": "PERCENTAGE"}],
        "capacityUntilFull": [{"rawValue": 80, "unit": "PERCENTAGE"}],
        "isCharging": False,
        "isPluggedIn": False,
    }

    with pytest.raises(helpers.SmartHomeError) as err:
        await trt.execute(trait.COMMAND_CHARGE, BASIC_DATA, {"charge": True}, {})
    assert err.value.code == const.ERR_FUNCTION_NOT_SUPPORTED

    with pytest.raises(helpers.SmartHomeError) as err:
        await trt.execute(trait.COMMAND_CHARGE, BASIC_DATA, {"charge": False}, {})
    assert err.value.code == const.ERR_FUNCTION_NOT_SUPPORTED


async def test_startstop_vacuum(hass: HomeAssistant) -> None:
    """Test startStop trait support for vacuum domain."""
    assert helpers.get_google_type(vacuum.DOMAIN, None) is not None
    assert trait.StartStopTrait.supported(vacuum.DOMAIN, 0, None, None)

    trt = trait.StartStopTrait(
        hass,
        State(
            "vacuum.bla",
            vacuum.STATE_PAUSED,
            {ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.PAUSE},
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {"pausable": True}

    assert trt.query_attributes() == {"isRunning": False, "isPaused": True}

    start_calls = async_mock_service(hass, vacuum.DOMAIN, vacuum.SERVICE_START)
    await trt.execute(trait.COMMAND_STARTSTOP, BASIC_DATA, {"start": True}, {})
    assert len(start_calls) == 1
    assert start_calls[0].data == {ATTR_ENTITY_ID: "vacuum.bla"}

    stop_calls = async_mock_service(hass, vacuum.DOMAIN, vacuum.SERVICE_STOP)
    await trt.execute(trait.COMMAND_STARTSTOP, BASIC_DATA, {"start": False}, {})
    assert len(stop_calls) == 1
    assert stop_calls[0].data == {ATTR_ENTITY_ID: "vacuum.bla"}

    pause_calls = async_mock_service(hass, vacuum.DOMAIN, vacuum.SERVICE_PAUSE)
    await trt.execute(trait.COMMAND_PAUSEUNPAUSE, BASIC_DATA, {"pause": True}, {})
    assert len(pause_calls) == 1
    assert pause_calls[0].data == {ATTR_ENTITY_ID: "vacuum.bla"}

    unpause_calls = async_mock_service(hass, vacuum.DOMAIN, vacuum.SERVICE_START)
    await trt.execute(trait.COMMAND_PAUSEUNPAUSE, BASIC_DATA, {"pause": False}, {})
    assert len(unpause_calls) == 1
    assert unpause_calls[0].data == {ATTR_ENTITY_ID: "vacuum.bla"}


async def test_startstop_cover(hass: HomeAssistant) -> None:
    """Test startStop trait support for cover domain."""
    assert helpers.get_google_type(cover.DOMAIN, None) is not None
    assert trait.StartStopTrait.supported(
        cover.DOMAIN, CoverEntityFeature.STOP, None, None
    )

    state = State(
        "cover.bla",
        cover.STATE_CLOSED,
        {ATTR_SUPPORTED_FEATURES: CoverEntityFeature.STOP},
    )

    trt = trait.StartStopTrait(
        hass,
        state,
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {}

    for state_value in (cover.STATE_CLOSING, cover.STATE_OPENING):
        state.state = state_value
        assert trt.query_attributes() == {"isRunning": True}

    stop_calls = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_STOP_COVER)
    await trt.execute(trait.COMMAND_STARTSTOP, BASIC_DATA, {"start": False}, {})
    assert len(stop_calls) == 1
    assert stop_calls[0].data == {ATTR_ENTITY_ID: "cover.bla"}

    for state_value in (cover.STATE_CLOSED, cover.STATE_OPEN):
        state.state = state_value
        assert trt.query_attributes() == {"isRunning": False}

    with pytest.raises(SmartHomeError, match="Cover is already stopped"):
        await trt.execute(trait.COMMAND_STARTSTOP, BASIC_DATA, {"start": False}, {})

    with pytest.raises(SmartHomeError, match="Starting a cover is not supported"):
        await trt.execute(trait.COMMAND_STARTSTOP, BASIC_DATA, {"start": True}, {})

    with pytest.raises(
        SmartHomeError,
        match="Command action.devices.commands.PauseUnpause is not supported",
    ):
        await trt.execute(trait.COMMAND_PAUSEUNPAUSE, BASIC_DATA, {"start": True}, {})


async def test_startstop_cover_assumed(hass: HomeAssistant) -> None:
    """Test startStop trait support for cover domain of assumed state."""
    trt = trait.StartStopTrait(
        hass,
        State(
            "cover.bla",
            cover.STATE_CLOSED,
            {
                ATTR_SUPPORTED_FEATURES: CoverEntityFeature.STOP,
                ATTR_ASSUMED_STATE: True,
            },
        ),
        BASIC_CONFIG,
    )

    stop_calls = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_STOP_COVER)
    await trt.execute(trait.COMMAND_STARTSTOP, BASIC_DATA, {"start": False}, {})
    assert len(stop_calls) == 1
    assert stop_calls[0].data == {ATTR_ENTITY_ID: "cover.bla"}


@pytest.mark.parametrize("supported_color_modes", [["hs"], ["rgb"], ["xy"]])
async def test_color_setting_color_light(
    hass: HomeAssistant, supported_color_modes
) -> None:
    """Test ColorSpectrum trait support for light domain."""
    assert helpers.get_google_type(light.DOMAIN, None) is not None
    assert not trait.ColorSettingTrait.supported(light.DOMAIN, 0, None, {})
    assert trait.ColorSettingTrait.supported(
        light.DOMAIN, 0, None, {"supported_color_modes": supported_color_modes}
    )

    trt = trait.ColorSettingTrait(
        hass,
        State(
            "light.bla",
            STATE_ON,
            {
                light.ATTR_HS_COLOR: (20, 94),
                light.ATTR_BRIGHTNESS: 200,
                light.ATTR_COLOR_MODE: "hs",
                "supported_color_modes": supported_color_modes,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {"colorModel": "hsv"}

    assert trt.query_attributes() == {
        "color": {"spectrumHsv": {"hue": 20, "saturation": 0.94, "value": 200 / 255}}
    }

    assert trt.can_execute(
        trait.COMMAND_COLOR_ABSOLUTE, {"color": {"spectrumRGB": 16715792}}
    )

    calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
    await trt.execute(
        trait.COMMAND_COLOR_ABSOLUTE,
        BASIC_DATA,
        {"color": {"spectrumRGB": 1052927}},
        {},
    )
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "light.bla",
        light.ATTR_HS_COLOR: (240, 93.725),
    }

    await trt.execute(
        trait.COMMAND_COLOR_ABSOLUTE,
        BASIC_DATA,
        {"color": {"spectrumHSV": {"hue": 100, "saturation": 0.50, "value": 0.20}}},
        {},
    )
    assert len(calls) == 2
    assert calls[1].data == {
        ATTR_ENTITY_ID: "light.bla",
        light.ATTR_HS_COLOR: [100, 50],
        light.ATTR_BRIGHTNESS: 0.2 * 255,
    }


async def test_color_setting_temperature_light(hass: HomeAssistant) -> None:
    """Test ColorTemperature trait support for light domain."""
    assert helpers.get_google_type(light.DOMAIN, None) is not None
    assert not trait.ColorSettingTrait.supported(light.DOMAIN, 0, None, {})
    assert trait.ColorSettingTrait.supported(
        light.DOMAIN, 0, None, {"supported_color_modes": ["color_temp"]}
    )

    trt = trait.ColorSettingTrait(
        hass,
        State(
            "light.bla",
            STATE_ON,
            {
                light.ATTR_MIN_MIREDS: 200,
                light.ATTR_COLOR_MODE: "color_temp",
                light.ATTR_COLOR_TEMP: 300,
                light.ATTR_MAX_MIREDS: 500,
                "supported_color_modes": ["color_temp"],
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "colorTemperatureRange": {"temperatureMinK": 2000, "temperatureMaxK": 5000}
    }

    assert trt.query_attributes() == {"color": {"temperatureK": 3333}}

    assert trt.can_execute(
        trait.COMMAND_COLOR_ABSOLUTE, {"color": {"temperature": 400}}
    )
    calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)

    with pytest.raises(helpers.SmartHomeError) as err:
        await trt.execute(
            trait.COMMAND_COLOR_ABSOLUTE,
            BASIC_DATA,
            {"color": {"temperature": 5555}},
            {},
        )
    assert err.value.code == const.ERR_VALUE_OUT_OF_RANGE

    await trt.execute(
        trait.COMMAND_COLOR_ABSOLUTE, BASIC_DATA, {"color": {"temperature": 2857}}, {}
    )
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "light.bla",
        light.ATTR_COLOR_TEMP: color.color_temperature_kelvin_to_mired(2857),
    }


async def test_color_light_temperature_light_bad_temp(hass: HomeAssistant) -> None:
    """Test ColorTemperature trait support for light domain."""
    assert helpers.get_google_type(light.DOMAIN, None) is not None
    assert not trait.ColorSettingTrait.supported(light.DOMAIN, 0, None, {})
    assert trait.ColorSettingTrait.supported(
        light.DOMAIN, 0, None, {"supported_color_modes": ["color_temp"]}
    )

    trt = trait.ColorSettingTrait(
        hass,
        State(
            "light.bla",
            STATE_ON,
            {
                light.ATTR_MIN_MIREDS: 200,
                light.ATTR_COLOR_TEMP: 0,
                light.ATTR_MAX_MIREDS: 500,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.query_attributes() == {}


async def test_light_modes(hass: HomeAssistant) -> None:
    """Test Light Mode trait."""
    assert helpers.get_google_type(light.DOMAIN, None) is not None
    assert trait.ModesTrait.supported(
        light.DOMAIN, LightEntityFeature.EFFECT, None, None
    )

    trt = trait.ModesTrait(
        hass,
        State(
            "light.living_room",
            light.STATE_ON,
            attributes={
                light.ATTR_EFFECT_LIST: ["random", "colorloop"],
                light.ATTR_EFFECT: "random",
            },
        ),
        BASIC_CONFIG,
    )

    attribs = trt.sync_attributes()
    assert attribs == {
        "availableModes": [
            {
                "name": "effect",
                "name_values": [{"name_synonym": ["effect"], "lang": "en"}],
                "settings": [
                    {
                        "setting_name": "random",
                        "setting_values": [
                            {"setting_synonym": ["random"], "lang": "en"}
                        ],
                    },
                    {
                        "setting_name": "colorloop",
                        "setting_values": [
                            {"setting_synonym": ["colorloop"], "lang": "en"}
                        ],
                    },
                ],
                "ordered": False,
            }
        ]
    }

    assert trt.query_attributes() == {
        "currentModeSettings": {"effect": "random"},
        "on": True,
    }

    assert trt.can_execute(
        trait.COMMAND_MODES,
        params={"updateModeSettings": {"effect": "colorloop"}},
    )

    calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
    await trt.execute(
        trait.COMMAND_MODES,
        BASIC_DATA,
        {"updateModeSettings": {"effect": "colorloop"}},
        {},
    )

    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": "light.living_room",
        "effect": "colorloop",
    }


@pytest.mark.parametrize(
    "component",
    [button, input_button],
)
async def test_scene_button(hass: HomeAssistant, component) -> None:
    """Test Scene trait support for the (input) button domain."""
    assert helpers.get_google_type(component.DOMAIN, None) is not None
    assert trait.SceneTrait.supported(component.DOMAIN, 0, None, None)

    trt = trait.SceneTrait(
        hass, State(f"{component.DOMAIN}.bla", STATE_UNKNOWN), BASIC_CONFIG
    )
    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {}
    assert trt.can_execute(trait.COMMAND_ACTIVATE_SCENE, {})

    calls = async_mock_service(hass, component.DOMAIN, component.SERVICE_PRESS)
    await trt.execute(trait.COMMAND_ACTIVATE_SCENE, BASIC_DATA, {}, {})

    # We don't wait till button press is done.
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: f"{component.DOMAIN}.bla"}


async def test_scene_scene(hass: HomeAssistant) -> None:
    """Test Scene trait support for scene domain."""
    assert helpers.get_google_type(scene.DOMAIN, None) is not None
    assert trait.SceneTrait.supported(scene.DOMAIN, 0, None, None)

    trt = trait.SceneTrait(hass, State("scene.bla", STATE_UNKNOWN), BASIC_CONFIG)
    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {}
    assert trt.can_execute(trait.COMMAND_ACTIVATE_SCENE, {})

    calls = async_mock_service(hass, scene.DOMAIN, SERVICE_TURN_ON)
    await trt.execute(trait.COMMAND_ACTIVATE_SCENE, BASIC_DATA, {}, {})
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "scene.bla"}


async def test_scene_script(hass: HomeAssistant) -> None:
    """Test Scene trait support for script domain."""
    assert helpers.get_google_type(script.DOMAIN, None) is not None
    assert trait.SceneTrait.supported(script.DOMAIN, 0, None, None)

    trt = trait.SceneTrait(hass, State("script.bla", STATE_OFF), BASIC_CONFIG)
    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {}
    assert trt.can_execute(trait.COMMAND_ACTIVATE_SCENE, {})

    calls = async_mock_service(hass, script.DOMAIN, SERVICE_TURN_ON)
    await trt.execute(trait.COMMAND_ACTIVATE_SCENE, BASIC_DATA, {}, {})

    # We don't wait till script execution is done.
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "script.bla"}


async def test_temperature_setting_climate_onoff(hass: HomeAssistant) -> None:
    """Test TemperatureSetting trait support for climate domain - range."""
    assert helpers.get_google_type(climate.DOMAIN, None) is not None
    assert trait.TemperatureSettingTrait.supported(climate.DOMAIN, 0, None, None)

    hass.config.units.temperature_unit = UnitOfTemperature.FAHRENHEIT

    trt = trait.TemperatureSettingTrait(
        hass,
        State(
            "climate.bla",
            climate.HVACMode.AUTO,
            {
                ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
                climate.ATTR_HVAC_MODES: [
                    climate.HVACMode.OFF,
                    climate.HVACMode.COOL,
                    climate.HVACMode.HEAT,
                    climate.HVACMode.HEAT_COOL,
                ],
                climate.ATTR_MIN_TEMP: 45,
                climate.ATTR_MAX_TEMP: 95,
            },
        ),
        BASIC_CONFIG,
    )
    assert trt.sync_attributes() == {
        "availableThermostatModes": ["off", "cool", "heat", "heatcool", "on"],
        "thermostatTemperatureRange": {
            "minThresholdCelsius": 7,
            "maxThresholdCelsius": 35,
        },
        "thermostatTemperatureUnit": "F",
    }
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_SET_MODE, {})

    calls = async_mock_service(hass, climate.DOMAIN, SERVICE_TURN_ON)
    await trt.execute(
        trait.COMMAND_THERMOSTAT_SET_MODE, BASIC_DATA, {"thermostatMode": "on"}, {}
    )
    assert len(calls) == 1

    calls = async_mock_service(hass, climate.DOMAIN, SERVICE_TURN_OFF)
    await trt.execute(
        trait.COMMAND_THERMOSTAT_SET_MODE, BASIC_DATA, {"thermostatMode": "off"}, {}
    )
    assert len(calls) == 1


async def test_temperature_setting_climate_no_modes(hass: HomeAssistant) -> None:
    """Test TemperatureSetting trait support for climate domain not supporting any modes."""
    assert helpers.get_google_type(climate.DOMAIN, None) is not None
    assert trait.TemperatureSettingTrait.supported(climate.DOMAIN, 0, None, None)

    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS

    trt = trait.TemperatureSettingTrait(
        hass,
        State(
            "climate.bla",
            climate.HVACMode.AUTO,
            {
                climate.ATTR_HVAC_MODES: [],
                climate.ATTR_MIN_TEMP: climate.DEFAULT_MIN_TEMP,
                climate.ATTR_MAX_TEMP: climate.DEFAULT_MAX_TEMP,
            },
        ),
        BASIC_CONFIG,
    )
    assert trt.sync_attributes() == {
        "availableThermostatModes": ["heat"],
        "thermostatTemperatureRange": {
            "minThresholdCelsius": climate.DEFAULT_MIN_TEMP,
            "maxThresholdCelsius": climate.DEFAULT_MAX_TEMP,
        },
        "thermostatTemperatureUnit": "C",
    }


async def test_temperature_setting_climate_range(hass: HomeAssistant) -> None:
    """Test TemperatureSetting trait support for climate domain - range."""
    assert helpers.get_google_type(climate.DOMAIN, None) is not None
    assert trait.TemperatureSettingTrait.supported(climate.DOMAIN, 0, None, None)

    hass.config.units.temperature_unit = UnitOfTemperature.FAHRENHEIT

    trt = trait.TemperatureSettingTrait(
        hass,
        State(
            "climate.bla",
            climate.HVACMode.AUTO,
            {
                climate.ATTR_CURRENT_TEMPERATURE: 70,
                climate.ATTR_CURRENT_HUMIDITY: 25,
                ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
                climate.ATTR_HVAC_MODES: [
                    STATE_OFF,
                    climate.HVACMode.COOL,
                    climate.HVACMode.HEAT,
                    climate.HVACMode.AUTO,
                ],
                climate.ATTR_TARGET_TEMP_HIGH: 75,
                climate.ATTR_TARGET_TEMP_LOW: 65,
                climate.ATTR_MIN_TEMP: 50,
                climate.ATTR_MAX_TEMP: 80,
            },
        ),
        BASIC_CONFIG,
    )
    assert trt.sync_attributes() == {
        "availableThermostatModes": ["off", "cool", "heat", "auto", "on"],
        "thermostatTemperatureRange": {
            "minThresholdCelsius": 10,
            "maxThresholdCelsius": 27,
        },
        "thermostatTemperatureUnit": "F",
    }
    assert trt.query_attributes() == {
        "thermostatMode": "auto",
        "thermostatTemperatureAmbient": 21.1,
        "thermostatHumidityAmbient": 25,
        "thermostatTemperatureSetpointLow": 18.3,
        "thermostatTemperatureSetpointHigh": 23.9,
    }
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE, {})
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_SET_MODE, {})

    calls = async_mock_service(hass, climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE)
    await trt.execute(
        trait.COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE,
        BASIC_DATA,
        {
            "thermostatTemperatureSetpointHigh": 25,
            "thermostatTemperatureSetpointLow": 20,
        },
        {},
    )
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "climate.bla",
        climate.ATTR_TARGET_TEMP_HIGH: 77,
        climate.ATTR_TARGET_TEMP_LOW: 68,
    }

    calls = async_mock_service(hass, climate.DOMAIN, climate.SERVICE_SET_HVAC_MODE)
    await trt.execute(
        trait.COMMAND_THERMOSTAT_SET_MODE, BASIC_DATA, {"thermostatMode": "cool"}, {}
    )
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "climate.bla",
        climate.ATTR_HVAC_MODE: climate.HVACMode.COOL,
    }

    with pytest.raises(helpers.SmartHomeError) as err:
        await trt.execute(
            trait.COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE,
            BASIC_DATA,
            {
                "thermostatTemperatureSetpointHigh": 26,
                "thermostatTemperatureSetpointLow": -100,
            },
            {},
        )
    assert err.value.code == const.ERR_VALUE_OUT_OF_RANGE

    with pytest.raises(helpers.SmartHomeError) as err:
        await trt.execute(
            trait.COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE,
            BASIC_DATA,
            {
                "thermostatTemperatureSetpointHigh": 100,
                "thermostatTemperatureSetpointLow": 18,
            },
            {},
        )
    assert err.value.code == const.ERR_VALUE_OUT_OF_RANGE

    calls = async_mock_service(hass, climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE)
    await trt.execute(
        trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT,
        BASIC_DATA,
        {"thermostatTemperatureSetpoint": 23.9},
        {},
    )
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "climate.bla",
        climate.ATTR_TEMPERATURE: 75,
    }
    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS


async def test_temperature_setting_climate_setpoint(hass: HomeAssistant) -> None:
    """Test TemperatureSetting trait support for climate domain - setpoint."""
    assert helpers.get_google_type(climate.DOMAIN, None) is not None
    assert trait.TemperatureSettingTrait.supported(climate.DOMAIN, 0, None, None)

    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS

    trt = trait.TemperatureSettingTrait(
        hass,
        State(
            "climate.bla",
            climate.HVACMode.COOL,
            {
                ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
                climate.ATTR_HVAC_MODES: [STATE_OFF, climate.HVACMode.COOL],
                climate.ATTR_MIN_TEMP: 10,
                climate.ATTR_MAX_TEMP: 30,
                climate.ATTR_PRESET_MODE: climate.PRESET_ECO,
                ATTR_TEMPERATURE: 18,
                climate.ATTR_CURRENT_TEMPERATURE: 20,
            },
        ),
        BASIC_CONFIG,
    )
    assert trt.sync_attributes() == {
        "availableThermostatModes": ["off", "cool", "on"],
        "thermostatTemperatureRange": {
            "minThresholdCelsius": 10,
            "maxThresholdCelsius": 30,
        },
        "thermostatTemperatureUnit": "C",
    }
    assert trt.query_attributes() == {
        "thermostatMode": "eco",
        "thermostatTemperatureAmbient": 20,
        "thermostatTemperatureSetpoint": 18,
    }
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, {})
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_SET_MODE, {})

    calls = async_mock_service(hass, climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE)
    with pytest.raises(helpers.SmartHomeError):
        await trt.execute(
            trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT,
            BASIC_DATA,
            {"thermostatTemperatureSetpoint": -100},
            {},
        )

    await trt.execute(
        trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT,
        BASIC_DATA,
        {"thermostatTemperatureSetpoint": 19},
        {},
    )
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "climate.bla", ATTR_TEMPERATURE: 19}

    calls = async_mock_service(hass, climate.DOMAIN, climate.SERVICE_SET_PRESET_MODE)
    await trt.execute(
        trait.COMMAND_THERMOSTAT_SET_MODE,
        BASIC_DATA,
        {"thermostatMode": "eco"},
        {},
    )
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "climate.bla",
        climate.ATTR_PRESET_MODE: "eco",
    }

    calls = async_mock_service(hass, climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE)
    await trt.execute(
        trait.COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE,
        BASIC_DATA,
        {
            "thermostatTemperatureSetpointHigh": 15,
            "thermostatTemperatureSetpointLow": 22,
        },
        {},
    )
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "climate.bla", ATTR_TEMPERATURE: 18.5}


async def test_temperature_setting_climate_setpoint_auto(hass: HomeAssistant) -> None:
    """Test TemperatureSetting trait support for climate domain.

    Setpoint in auto mode.
    """
    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS

    trt = trait.TemperatureSettingTrait(
        hass,
        State(
            "climate.bla",
            climate.HVACMode.HEAT_COOL,
            {
                climate.ATTR_HVAC_MODES: [
                    climate.HVACMode.OFF,
                    climate.HVACMode.HEAT_COOL,
                ],
                climate.ATTR_MIN_TEMP: 10,
                climate.ATTR_MAX_TEMP: 30,
                ATTR_TEMPERATURE: 18,
                climate.ATTR_CURRENT_TEMPERATURE: 20,
            },
        ),
        BASIC_CONFIG,
    )
    assert trt.sync_attributes() == {
        "availableThermostatModes": ["off", "heatcool", "on"],
        "thermostatTemperatureRange": {
            "minThresholdCelsius": 10,
            "maxThresholdCelsius": 30,
        },
        "thermostatTemperatureUnit": "C",
    }
    assert trt.query_attributes() == {
        "thermostatMode": "heatcool",
        "thermostatTemperatureAmbient": 20,
        "thermostatTemperatureSetpointHigh": 18,
        "thermostatTemperatureSetpointLow": 18,
    }
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, {})
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_SET_MODE, {})

    calls = async_mock_service(hass, climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE)

    await trt.execute(
        trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT,
        BASIC_DATA,
        {"thermostatTemperatureSetpoint": 19},
        {},
    )
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "climate.bla", ATTR_TEMPERATURE: 19}


async def test_temperature_control(hass: HomeAssistant) -> None:
    """Test TemperatureControl trait support for sensor domain."""
    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS

    trt = trait.TemperatureControlTrait(
        hass,
        State("sensor.temp", 18),
        BASIC_CONFIG,
    )
    assert trt.sync_attributes() == {
        "queryOnlyTemperatureControl": True,
        "temperatureUnitForUX": "C",
        "temperatureRange": {"maxThresholdCelsius": 100, "minThresholdCelsius": -100},
    }
    assert trt.query_attributes() == {
        "temperatureSetpointCelsius": 18,
        "temperatureAmbientCelsius": 18,
    }
    with pytest.raises(helpers.SmartHomeError) as err:
        await trt.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": False}, {})
    assert err.value.code == const.ERR_NOT_SUPPORTED


async def test_humidity_setting_humidifier_setpoint(hass: HomeAssistant) -> None:
    """Test HumiditySetting trait support for humidifier domain - setpoint."""
    assert helpers.get_google_type(humidifier.DOMAIN, None) is not None
    assert trait.HumiditySettingTrait.supported(humidifier.DOMAIN, 0, None, None)

    trt = trait.HumiditySettingTrait(
        hass,
        State(
            "humidifier.bla",
            STATE_ON,
            {
                humidifier.ATTR_MIN_HUMIDITY: 20,
                humidifier.ATTR_MAX_HUMIDITY: 90,
                humidifier.ATTR_HUMIDITY: 38,
                humidifier.ATTR_CURRENT_HUMIDITY: 30,
            },
        ),
        BASIC_CONFIG,
    )
    assert trt.sync_attributes() == {
        "humiditySetpointRange": {"minPercent": 20, "maxPercent": 90}
    }
    assert trt.query_attributes() == {
        "humiditySetpointPercent": 38,
        "humidityAmbientPercent": 30,
    }
    assert trt.can_execute(trait.COMMAND_SET_HUMIDITY, {})

    calls = async_mock_service(hass, humidifier.DOMAIN, humidifier.SERVICE_SET_HUMIDITY)

    await trt.execute(trait.COMMAND_SET_HUMIDITY, BASIC_DATA, {"humidity": 32}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "humidifier.bla",
        humidifier.ATTR_HUMIDITY: 32,
    }


async def test_lock_unlock_lock(hass: HomeAssistant) -> None:
    """Test LockUnlock trait locking support for lock domain."""
    assert helpers.get_google_type(lock.DOMAIN, None) is not None
    assert trait.LockUnlockTrait.supported(
        lock.DOMAIN, LockEntityFeature.OPEN, None, None
    )
    assert trait.LockUnlockTrait.might_2fa(lock.DOMAIN, LockEntityFeature.OPEN, None)

    trt = trait.LockUnlockTrait(
        hass, State("lock.front_door", lock.STATE_LOCKED), PIN_CONFIG
    )

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {"isLocked": True}

    assert trt.can_execute(trait.COMMAND_LOCKUNLOCK, {"lock": True})

    calls = async_mock_service(hass, lock.DOMAIN, lock.SERVICE_LOCK)

    await trt.execute(trait.COMMAND_LOCKUNLOCK, PIN_DATA, {"lock": True}, {})

    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "lock.front_door"}


async def test_lock_unlock_unlocking(hass: HomeAssistant) -> None:
    """Test LockUnlock trait locking support for lock domain."""
    assert helpers.get_google_type(lock.DOMAIN, None) is not None
    assert trait.LockUnlockTrait.supported(
        lock.DOMAIN, LockEntityFeature.OPEN, None, None
    )
    assert trait.LockUnlockTrait.might_2fa(lock.DOMAIN, LockEntityFeature.OPEN, None)

    trt = trait.LockUnlockTrait(
        hass, State("lock.front_door", lock.STATE_UNLOCKING), PIN_CONFIG
    )

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {"isLocked": True}


async def test_lock_unlock_lock_jammed(hass: HomeAssistant) -> None:
    """Test LockUnlock trait locking support for lock domain that jams."""
    assert helpers.get_google_type(lock.DOMAIN, None) is not None
    assert trait.LockUnlockTrait.supported(
        lock.DOMAIN, LockEntityFeature.OPEN, None, None
    )
    assert trait.LockUnlockTrait.might_2fa(lock.DOMAIN, LockEntityFeature.OPEN, None)

    trt = trait.LockUnlockTrait(
        hass, State("lock.front_door", lock.STATE_JAMMED), PIN_CONFIG
    )

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {"isJammed": True}

    assert trt.can_execute(trait.COMMAND_LOCKUNLOCK, {"lock": True})

    calls = async_mock_service(hass, lock.DOMAIN, lock.SERVICE_LOCK)

    await trt.execute(trait.COMMAND_LOCKUNLOCK, PIN_DATA, {"lock": True}, {})

    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "lock.front_door"}


async def test_lock_unlock_unlock(hass: HomeAssistant) -> None:
    """Test LockUnlock trait unlocking support for lock domain."""
    assert helpers.get_google_type(lock.DOMAIN, None) is not None
    assert trait.LockUnlockTrait.supported(
        lock.DOMAIN, LockEntityFeature.OPEN, None, None
    )

    trt = trait.LockUnlockTrait(
        hass, State("lock.front_door", lock.STATE_LOCKED), PIN_CONFIG
    )

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {"isLocked": True}

    assert trt.can_execute(trait.COMMAND_LOCKUNLOCK, {"lock": False})

    calls = async_mock_service(hass, lock.DOMAIN, lock.SERVICE_UNLOCK)

    # No challenge data
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(trait.COMMAND_LOCKUNLOCK, PIN_DATA, {"lock": False}, {})
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_PIN_NEEDED

    # invalid pin
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(
            trait.COMMAND_LOCKUNLOCK, PIN_DATA, {"lock": False}, {"pin": 9999}
        )
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_FAILED_PIN_NEEDED

    await trt.execute(
        trait.COMMAND_LOCKUNLOCK, PIN_DATA, {"lock": False}, {"pin": "1234"}
    )

    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "lock.front_door"}

    # Test without pin
    trt = trait.LockUnlockTrait(
        hass, State("lock.front_door", lock.STATE_LOCKED), BASIC_CONFIG
    )

    with pytest.raises(error.SmartHomeError) as err:
        await trt.execute(trait.COMMAND_LOCKUNLOCK, BASIC_DATA, {"lock": False}, {})
    assert len(calls) == 1
    assert err.value.code == const.ERR_CHALLENGE_NOT_SETUP

    # Test with 2FA override
    with patch.object(
        BASIC_CONFIG,
        "should_2fa",
        return_value=False,
    ):
        await trt.execute(trait.COMMAND_LOCKUNLOCK, BASIC_DATA, {"lock": False}, {})
    assert len(calls) == 2


async def test_arm_disarm_arm_away(hass: HomeAssistant) -> None:
    """Test ArmDisarm trait Arming support for alarm_control_panel domain."""
    assert helpers.get_google_type(alarm_control_panel.DOMAIN, None) is not None
    assert trait.ArmDisArmTrait.supported(alarm_control_panel.DOMAIN, 0, None, None)
    assert trait.ArmDisArmTrait.might_2fa(alarm_control_panel.DOMAIN, 0, None)

    trt = trait.ArmDisArmTrait(
        hass,
        State(
            "alarm_control_panel.alarm",
            STATE_ALARM_ARMED_AWAY,
            {
                alarm_control_panel.ATTR_CODE_ARM_REQUIRED: True,
                ATTR_SUPPORTED_FEATURES: AlarmControlPanelEntityFeature.ARM_HOME
                | AlarmControlPanelEntityFeature.ARM_AWAY,
            },
        ),
        PIN_CONFIG,
    )
    assert trt.sync_attributes() == {
        "availableArmLevels": {
            "levels": [
                {
                    "level_name": "armed_home",
                    "level_values": [
                        {"level_synonym": ["armed home", "home"], "lang": "en"}
                    ],
                },
                {
                    "level_name": "armed_away",
                    "level_values": [
                        {"level_synonym": ["armed away", "away"], "lang": "en"}
                    ],
                },
            ],
            "ordered": False,
        }
    }

    assert trt.query_attributes() == {
        "isArmed": True,
        "currentArmLevel": STATE_ALARM_ARMED_AWAY,
    }

    assert trt.can_execute(
        trait.COMMAND_ARMDISARM, {"arm": True, "armLevel": STATE_ALARM_ARMED_AWAY}
    )

    calls = async_mock_service(
        hass, alarm_control_panel.DOMAIN, alarm_control_panel.SERVICE_ALARM_ARM_AWAY
    )

    # Test with no secure_pin configured

    with pytest.raises(error.SmartHomeError) as err:
        trt = trait.ArmDisArmTrait(
            hass,
            State(
                "alarm_control_panel.alarm",
                STATE_ALARM_DISARMED,
                {alarm_control_panel.ATTR_CODE_ARM_REQUIRED: True},
            ),
            BASIC_CONFIG,
        )
        await trt.execute(
            trait.COMMAND_ARMDISARM,
            BASIC_DATA,
            {"arm": True, "armLevel": STATE_ALARM_ARMED_AWAY},
            {},
        )
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NOT_SETUP

    trt = trait.ArmDisArmTrait(
        hass,
        State(
            "alarm_control_panel.alarm",
            STATE_ALARM_DISARMED,
            {alarm_control_panel.ATTR_CODE_ARM_REQUIRED: True},
        ),
        PIN_CONFIG,
    )
    # No challenge data
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(
            trait.COMMAND_ARMDISARM,
            PIN_DATA,
            {"arm": True, "armLevel": STATE_ALARM_ARMED_AWAY},
            {},
        )
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_PIN_NEEDED

    # invalid pin
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(
            trait.COMMAND_ARMDISARM,
            PIN_DATA,
            {"arm": True, "armLevel": STATE_ALARM_ARMED_AWAY},
            {"pin": 9999},
        )
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_FAILED_PIN_NEEDED

    # correct pin
    await trt.execute(
        trait.COMMAND_ARMDISARM,
        PIN_DATA,
        {"arm": True, "armLevel": STATE_ALARM_ARMED_AWAY},
        {"pin": "1234"},
    )

    assert len(calls) == 1

    # Test already armed
    with pytest.raises(error.SmartHomeError) as err:
        trt = trait.ArmDisArmTrait(
            hass,
            State(
                "alarm_control_panel.alarm",
                STATE_ALARM_ARMED_AWAY,
                {alarm_control_panel.ATTR_CODE_ARM_REQUIRED: True},
            ),
            PIN_CONFIG,
        )
        await trt.execute(
            trait.COMMAND_ARMDISARM,
            PIN_DATA,
            {"arm": True, "armLevel": STATE_ALARM_ARMED_AWAY},
            {},
        )
    assert len(calls) == 1
    assert err.value.code == const.ERR_ALREADY_ARMED

    # Test with code_arm_required False
    trt = trait.ArmDisArmTrait(
        hass,
        State(
            "alarm_control_panel.alarm",
            STATE_ALARM_DISARMED,
            {alarm_control_panel.ATTR_CODE_ARM_REQUIRED: False},
        ),
        PIN_CONFIG,
    )
    await trt.execute(
        trait.COMMAND_ARMDISARM,
        PIN_DATA,
        {"arm": True, "armLevel": STATE_ALARM_ARMED_AWAY},
        {},
    )
    assert len(calls) == 2

    with pytest.raises(error.SmartHomeError) as err:
        await trt.execute(
            trait.COMMAND_ARMDISARM,
            PIN_DATA,
            {"arm": True},
            {},
        )


async def test_arm_disarm_disarm(hass: HomeAssistant) -> None:
    """Test ArmDisarm trait Disarming support for alarm_control_panel domain."""
    assert helpers.get_google_type(alarm_control_panel.DOMAIN, None) is not None
    assert trait.ArmDisArmTrait.supported(alarm_control_panel.DOMAIN, 0, None, None)
    assert trait.ArmDisArmTrait.might_2fa(alarm_control_panel.DOMAIN, 0, None)

    trt = trait.ArmDisArmTrait(
        hass,
        State(
            "alarm_control_panel.alarm",
            STATE_ALARM_DISARMED,
            {
                alarm_control_panel.ATTR_CODE_ARM_REQUIRED: True,
                ATTR_SUPPORTED_FEATURES: AlarmControlPanelEntityFeature.TRIGGER
                | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS,
            },
        ),
        PIN_CONFIG,
    )
    assert trt.sync_attributes() == {
        "availableArmLevels": {
            "levels": [
                {
                    "level_name": "armed_custom_bypass",
                    "level_values": [
                        {
                            "level_synonym": ["armed custom bypass", "custom"],
                            "lang": "en",
                        }
                    ],
                },
                {
                    "level_name": "triggered",
                    "level_values": [{"level_synonym": ["triggered"], "lang": "en"}],
                },
            ],
            "ordered": False,
        }
    }

    assert trt.query_attributes() == {"isArmed": False}

    assert trt.can_execute(trait.COMMAND_ARMDISARM, {"arm": False})

    calls = async_mock_service(
        hass, alarm_control_panel.DOMAIN, alarm_control_panel.SERVICE_ALARM_DISARM
    )

    # Test without secure_pin configured
    with pytest.raises(error.SmartHomeError) as err:
        trt = trait.ArmDisArmTrait(
            hass,
            State(
                "alarm_control_panel.alarm",
                STATE_ALARM_ARMED_AWAY,
                {alarm_control_panel.ATTR_CODE_ARM_REQUIRED: True},
            ),
            BASIC_CONFIG,
        )
        await trt.execute(trait.COMMAND_ARMDISARM, BASIC_DATA, {"arm": False}, {})

    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NOT_SETUP

    trt = trait.ArmDisArmTrait(
        hass,
        State(
            "alarm_control_panel.alarm",
            STATE_ALARM_ARMED_AWAY,
            {alarm_control_panel.ATTR_CODE_ARM_REQUIRED: True},
        ),
        PIN_CONFIG,
    )

    # No challenge data
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(trait.COMMAND_ARMDISARM, PIN_DATA, {"arm": False}, {})
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_PIN_NEEDED

    # invalid pin
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(
            trait.COMMAND_ARMDISARM, PIN_DATA, {"arm": False}, {"pin": 9999}
        )
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_FAILED_PIN_NEEDED

    # correct pin
    await trt.execute(
        trait.COMMAND_ARMDISARM, PIN_DATA, {"arm": False}, {"pin": "1234"}
    )

    assert len(calls) == 1

    # Test already disarmed
    with pytest.raises(error.SmartHomeError) as err:
        trt = trait.ArmDisArmTrait(
            hass,
            State(
                "alarm_control_panel.alarm",
                STATE_ALARM_DISARMED,
                {alarm_control_panel.ATTR_CODE_ARM_REQUIRED: True},
            ),
            PIN_CONFIG,
        )
        await trt.execute(trait.COMMAND_ARMDISARM, PIN_DATA, {"arm": False}, {})
    assert len(calls) == 1
    assert err.value.code == const.ERR_ALREADY_DISARMED

    # Cancel arming after already armed will require pin
    with pytest.raises(error.SmartHomeError) as err:
        trt = trait.ArmDisArmTrait(
            hass,
            State(
                "alarm_control_panel.alarm",
                STATE_ALARM_ARMED_AWAY,
                {alarm_control_panel.ATTR_CODE_ARM_REQUIRED: False},
            ),
            PIN_CONFIG,
        )
        await trt.execute(
            trait.COMMAND_ARMDISARM, PIN_DATA, {"arm": True, "cancel": True}, {}
        )
    assert len(calls) == 1
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_PIN_NEEDED

    # Cancel arming while pending to arm doesn't require pin
    trt = trait.ArmDisArmTrait(
        hass,
        State(
            "alarm_control_panel.alarm",
            STATE_ALARM_PENDING,
            {alarm_control_panel.ATTR_CODE_ARM_REQUIRED: False},
        ),
        PIN_CONFIG,
    )
    await trt.execute(
        trait.COMMAND_ARMDISARM, PIN_DATA, {"arm": True, "cancel": True}, {}
    )
    assert len(calls) == 2


async def test_fan_speed(hass: HomeAssistant) -> None:
    """Test FanSpeed trait speed control support for fan domain."""
    assert helpers.get_google_type(fan.DOMAIN, None) is not None
    assert trait.FanSpeedTrait.supported(
        fan.DOMAIN, FanEntityFeature.SET_SPEED, None, None
    )

    trt = trait.FanSpeedTrait(
        hass,
        State(
            "fan.living_room_fan",
            STATE_ON,
            attributes={
                "percentage": 33,
                "percentage_step": 1.0,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "reversible": False,
        "supportsFanSpeedPercent": True,
        "availableFanSpeeds": ANY,
    }

    assert trt.query_attributes() == {
        "currentFanSpeedPercent": 33,
        "currentFanSpeedSetting": ANY,
    }

    assert trt.can_execute(trait.COMMAND_FANSPEED, params={"fanSpeedPercent": 10})

    calls = async_mock_service(hass, fan.DOMAIN, fan.SERVICE_SET_PERCENTAGE)
    await trt.execute(trait.COMMAND_FANSPEED, BASIC_DATA, {"fanSpeedPercent": 10}, {})

    assert len(calls) == 1
    assert calls[0].data == {"entity_id": "fan.living_room_fan", "percentage": 10}


async def test_fan_speed_without_percentage_step(hass: HomeAssistant) -> None:
    """Test FanSpeed trait speed control percentage step for fan domain."""
    assert helpers.get_google_type(fan.DOMAIN, None) is not None
    assert trait.FanSpeedTrait.supported(
        fan.DOMAIN, FanEntityFeature.SET_SPEED, None, None
    )

    trt = trait.FanSpeedTrait(
        hass,
        State(
            "fan.living_room_fan",
            STATE_ON,
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "reversible": False,
        "supportsFanSpeedPercent": True,
        "availableFanSpeeds": ANY,
    }
    # If a fan state has (temporary) no percentage_step attribute return 1 available
    assert trt.query_attributes() == {
        "currentFanSpeedPercent": 0,
        "currentFanSpeedSetting": "1/5",
    }


@pytest.mark.parametrize(
    ("percentage", "percentage_step", "speed", "speeds", "percentage_result"),
    [
        (
            33,
            1.0,
            "2/5",
            [
                ["Low", "Min", "Slow", "1"],
                ["Medium Low", "2"],
                ["Medium", "3"],
                ["Medium High", "4"],
                ["High", "Max", "Fast", "5"],
            ],
            40,
        ),
        (
            40,
            1.0,
            "2/5",
            [
                ["Low", "Min", "Slow", "1"],
                ["Medium Low", "2"],
                ["Medium", "3"],
                ["Medium High", "4"],
                ["High", "Max", "Fast", "5"],
            ],
            40,
        ),
        (
            33,
            100 / 3,
            "1/3",
            [
                ["Low", "Min", "Slow", "1"],
                ["Medium", "2"],
                ["High", "Max", "Fast", "3"],
            ],
            33,
        ),
        (
            20,
            100 / 4,
            "1/4",
            [
                ["Low", "Min", "Slow", "1"],
                ["Medium Low", "2"],
                ["Medium High", "3"],
                ["High", "Max", "Fast", "4"],
            ],
            25,
        ),
    ],
)
async def test_fan_speed_ordered(
    hass,
    percentage: int,
    percentage_step: float,
    speed: str,
    speeds: list[list[str]],
    percentage_result: int,
):
    """Test FanSpeed trait speed control support for fan domain."""
    assert helpers.get_google_type(fan.DOMAIN, None) is not None
    assert trait.FanSpeedTrait.supported(
        fan.DOMAIN, FanEntityFeature.SET_SPEED, None, None
    )

    trt = trait.FanSpeedTrait(
        hass,
        State(
            "fan.living_room_fan",
            STATE_ON,
            attributes={
                "percentage": percentage,
                "percentage_step": percentage_step,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "reversible": False,
        "supportsFanSpeedPercent": True,
        "availableFanSpeeds": {
            "ordered": True,
            "speeds": [
                {
                    "speed_name": f"{idx+1}/{len(speeds)}",
                    "speed_values": [{"lang": "en", "speed_synonym": x}],
                }
                for idx, x in enumerate(speeds)
            ],
        },
    }

    assert trt.query_attributes() == {
        "currentFanSpeedPercent": percentage,
        "currentFanSpeedSetting": speed,
    }

    assert trt.can_execute(trait.COMMAND_FANSPEED, params={"fanSpeed": speed})

    calls = async_mock_service(hass, fan.DOMAIN, fan.SERVICE_SET_PERCENTAGE)
    await trt.execute(trait.COMMAND_FANSPEED, BASIC_DATA, {"fanSpeed": speed}, {})

    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": "fan.living_room_fan",
        "percentage": percentage_result,
    }


@pytest.mark.parametrize(
    ("direction_state", "direction_call"),
    [
        (fan.DIRECTION_FORWARD, fan.DIRECTION_REVERSE),
        (fan.DIRECTION_REVERSE, fan.DIRECTION_FORWARD),
        (None, fan.DIRECTION_FORWARD),
    ],
)
async def test_fan_reverse(
    hass: HomeAssistant, direction_state, direction_call
) -> None:
    """Test FanSpeed trait speed control support for fan domain."""

    calls = async_mock_service(hass, fan.DOMAIN, fan.SERVICE_SET_DIRECTION)

    trt = trait.FanSpeedTrait(
        hass,
        State(
            "fan.living_room_fan",
            STATE_ON,
            attributes={
                "percentage": 33,
                "percentage_step": 1.0,
                "direction": direction_state,
                "supported_features": FanEntityFeature.DIRECTION,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "reversible": True,
        "supportsFanSpeedPercent": True,
        "availableFanSpeeds": ANY,
    }

    assert trt.query_attributes() == {
        "currentFanSpeedPercent": 33,
        "currentFanSpeedSetting": ANY,
    }

    assert trt.can_execute(trait.COMMAND_REVERSE, params={})
    await trt.execute(trait.COMMAND_REVERSE, BASIC_DATA, {}, {})

    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": "fan.living_room_fan",
        "direction": direction_call,
    }


async def test_climate_fan_speed(hass: HomeAssistant) -> None:
    """Test FanSpeed trait speed control support for climate domain."""
    assert helpers.get_google_type(climate.DOMAIN, None) is not None
    assert trait.FanSpeedTrait.supported(
        climate.DOMAIN, ClimateEntityFeature.FAN_MODE, None, None
    )

    trt = trait.FanSpeedTrait(
        hass,
        State(
            "climate.living_room_ac",
            "on",
            attributes={
                "fan_modes": ["auto", "low", "medium", "high"],
                "fan_mode": "low",
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "availableFanSpeeds": {
            "ordered": True,
            "speeds": [
                {
                    "speed_name": "auto",
                    "speed_values": [{"speed_synonym": ["auto"], "lang": "en"}],
                },
                {
                    "speed_name": "low",
                    "speed_values": [{"speed_synonym": ["low"], "lang": "en"}],
                },
                {
                    "speed_name": "medium",
                    "speed_values": [{"speed_synonym": ["medium"], "lang": "en"}],
                },
                {
                    "speed_name": "high",
                    "speed_values": [{"speed_synonym": ["high"], "lang": "en"}],
                },
            ],
        },
        "reversible": False,
    }

    assert trt.query_attributes() == {
        "currentFanSpeedSetting": "low",
    }

    assert trt.can_execute(trait.COMMAND_FANSPEED, params={"fanSpeed": "medium"})

    calls = async_mock_service(hass, climate.DOMAIN, climate.SERVICE_SET_FAN_MODE)
    await trt.execute(trait.COMMAND_FANSPEED, BASIC_DATA, {"fanSpeed": "medium"}, {})

    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": "climate.living_room_ac",
        "fan_mode": "medium",
    }


async def test_inputselector(hass: HomeAssistant) -> None:
    """Test input selector trait."""
    assert helpers.get_google_type(media_player.DOMAIN, None) is not None
    assert trait.InputSelectorTrait.supported(
        media_player.DOMAIN,
        MediaPlayerEntityFeature.SELECT_SOURCE,
        None,
        None,
    )

    trt = trait.InputSelectorTrait(
        hass,
        State(
            "media_player.living_room",
            media_player.STATE_PLAYING,
            attributes={
                media_player.ATTR_INPUT_SOURCE_LIST: [
                    "media",
                    "game",
                    "chromecast",
                    "plex",
                ],
                media_player.ATTR_INPUT_SOURCE: "game",
            },
        ),
        BASIC_CONFIG,
    )

    attribs = trt.sync_attributes()
    assert attribs == {
        "availableInputs": [
            {"key": "media", "names": [{"name_synonym": ["media"], "lang": "en"}]},
            {"key": "game", "names": [{"name_synonym": ["game"], "lang": "en"}]},
            {
                "key": "chromecast",
                "names": [{"name_synonym": ["chromecast"], "lang": "en"}],
            },
            {"key": "plex", "names": [{"name_synonym": ["plex"], "lang": "en"}]},
        ],
        "orderedInputs": True,
    }

    assert trt.query_attributes() == {
        "currentInput": "game",
    }

    assert trt.can_execute(
        trait.COMMAND_INPUT,
        params={"newInput": "media"},
    )

    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_SELECT_SOURCE
    )
    await trt.execute(
        trait.COMMAND_INPUT,
        BASIC_DATA,
        {"newInput": "media"},
        {},
    )

    assert len(calls) == 1
    assert calls[0].data == {"entity_id": "media_player.living_room", "source": "media"}


@pytest.mark.parametrize(
    ("sources", "source", "source_next", "source_prev"),
    [
        (["a"], "a", "a", "a"),
        (["a", "b"], "a", "b", "b"),
        (["a", "b", "c"], "a", "b", "c"),
    ],
)
async def test_inputselector_nextprev(
    hass: HomeAssistant, sources, source, source_next, source_prev
) -> None:
    """Test input selector trait."""
    trt = trait.InputSelectorTrait(
        hass,
        State(
            "media_player.living_room",
            media_player.STATE_PLAYING,
            attributes={
                media_player.ATTR_INPUT_SOURCE_LIST: sources,
                media_player.ATTR_INPUT_SOURCE: source,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.can_execute("action.devices.commands.NextInput", params={})
    assert trt.can_execute("action.devices.commands.PreviousInput", params={})

    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_SELECT_SOURCE
    )
    await trt.execute(
        "action.devices.commands.NextInput",
        BASIC_DATA,
        {},
        {},
    )
    await trt.execute(
        "action.devices.commands.PreviousInput",
        BASIC_DATA,
        {},
        {},
    )

    assert len(calls) == 2
    assert calls[0].data == {
        "entity_id": "media_player.living_room",
        "source": source_next,
    }
    assert calls[1].data == {
        "entity_id": "media_player.living_room",
        "source": source_prev,
    }


@pytest.mark.parametrize(
    ("sources", "source"), [(None, "a"), (["a", "b"], None), (["a", "b"], "c")]
)
async def test_inputselector_nextprev_invalid(
    hass: HomeAssistant, sources, source
) -> None:
    """Test input selector trait."""
    trt = trait.InputSelectorTrait(
        hass,
        State(
            "media_player.living_room",
            media_player.STATE_PLAYING,
            attributes={
                media_player.ATTR_INPUT_SOURCE_LIST: sources,
                media_player.ATTR_INPUT_SOURCE: source,
            },
        ),
        BASIC_CONFIG,
    )

    with pytest.raises(SmartHomeError):
        await trt.execute(
            "action.devices.commands.NextInput",
            BASIC_DATA,
            {},
            {},
        )

    with pytest.raises(SmartHomeError):
        await trt.execute(
            "action.devices.commands.PreviousInput",
            BASIC_DATA,
            {},
            {},
        )

    with pytest.raises(SmartHomeError):
        await trt.execute(
            "action.devices.commands.InvalidCommand",
            BASIC_DATA,
            {},
            {},
        )


async def test_modes_input_select(hass: HomeAssistant) -> None:
    """Test Input Select Mode trait."""
    assert helpers.get_google_type(input_select.DOMAIN, None) is not None
    assert trait.ModesTrait.supported(input_select.DOMAIN, None, None, None)

    trt = trait.ModesTrait(
        hass,
        State("input_select.bla", "unavailable"),
        BASIC_CONFIG,
    )
    assert trt.sync_attributes() == {"availableModes": []}

    trt = trait.ModesTrait(
        hass,
        State(
            "input_select.bla",
            "abc",
            attributes={input_select.ATTR_OPTIONS: ["abc", "123", "xyz"]},
        ),
        BASIC_CONFIG,
    )

    attribs = trt.sync_attributes()
    assert attribs == {
        "availableModes": [
            {
                "name": "option",
                "name_values": [
                    {
                        "name_synonym": ["option", "setting", "mode", "value"],
                        "lang": "en",
                    }
                ],
                "settings": [
                    {
                        "setting_name": "abc",
                        "setting_values": [{"setting_synonym": ["abc"], "lang": "en"}],
                    },
                    {
                        "setting_name": "123",
                        "setting_values": [{"setting_synonym": ["123"], "lang": "en"}],
                    },
                    {
                        "setting_name": "xyz",
                        "setting_values": [{"setting_synonym": ["xyz"], "lang": "en"}],
                    },
                ],
                "ordered": False,
            }
        ]
    }

    assert trt.query_attributes() == {
        "currentModeSettings": {"option": "abc"},
        "on": True,
    }

    assert trt.can_execute(
        trait.COMMAND_MODES,
        params={"updateModeSettings": {"option": "xyz"}},
    )

    calls = async_mock_service(
        hass, input_select.DOMAIN, input_select.SERVICE_SELECT_OPTION
    )
    await trt.execute(
        trait.COMMAND_MODES,
        BASIC_DATA,
        {"updateModeSettings": {"option": "xyz"}},
        {},
    )

    assert len(calls) == 1
    assert calls[0].data == {"entity_id": "input_select.bla", "option": "xyz"}


async def test_modes_select(hass: HomeAssistant) -> None:
    """Test Select Mode trait."""
    assert helpers.get_google_type(select.DOMAIN, None) is not None
    assert trait.ModesTrait.supported(select.DOMAIN, None, None, None)

    trt = trait.ModesTrait(
        hass,
        State("select.bla", "unavailable"),
        BASIC_CONFIG,
    )
    assert trt.sync_attributes() == {"availableModes": []}

    trt = trait.ModesTrait(
        hass,
        State(
            "select.bla",
            "abc",
            attributes={select.ATTR_OPTIONS: ["abc", "123", "xyz"]},
        ),
        BASIC_CONFIG,
    )

    attribs = trt.sync_attributes()
    assert attribs == {
        "availableModes": [
            {
                "name": "option",
                "name_values": [
                    {
                        "name_synonym": ["option", "setting", "mode", "value"],
                        "lang": "en",
                    }
                ],
                "settings": [
                    {
                        "setting_name": "abc",
                        "setting_values": [{"setting_synonym": ["abc"], "lang": "en"}],
                    },
                    {
                        "setting_name": "123",
                        "setting_values": [{"setting_synonym": ["123"], "lang": "en"}],
                    },
                    {
                        "setting_name": "xyz",
                        "setting_values": [{"setting_synonym": ["xyz"], "lang": "en"}],
                    },
                ],
                "ordered": False,
            }
        ]
    }

    assert trt.query_attributes() == {
        "currentModeSettings": {"option": "abc"},
        "on": True,
    }

    assert trt.can_execute(
        trait.COMMAND_MODES,
        params={"updateModeSettings": {"option": "xyz"}},
    )

    calls = async_mock_service(hass, select.DOMAIN, select.SERVICE_SELECT_OPTION)
    await trt.execute(
        trait.COMMAND_MODES,
        BASIC_DATA,
        {"updateModeSettings": {"option": "xyz"}},
        {},
    )

    assert len(calls) == 1
    assert calls[0].data == {"entity_id": "select.bla", "option": "xyz"}


async def test_modes_humidifier(hass: HomeAssistant) -> None:
    """Test Humidifier Mode trait."""
    assert helpers.get_google_type(humidifier.DOMAIN, None) is not None
    assert trait.ModesTrait.supported(
        humidifier.DOMAIN, HumidifierEntityFeature.MODES, None, None
    )

    trt = trait.ModesTrait(
        hass,
        State(
            "humidifier.humidifier",
            STATE_OFF,
            attributes={
                humidifier.ATTR_AVAILABLE_MODES: [
                    humidifier.MODE_NORMAL,
                    humidifier.MODE_AUTO,
                    humidifier.MODE_AWAY,
                ],
                ATTR_SUPPORTED_FEATURES: humidifier.HumidifierEntityFeature.MODES,
                humidifier.ATTR_MIN_HUMIDITY: 30,
                humidifier.ATTR_MAX_HUMIDITY: 99,
                humidifier.ATTR_HUMIDITY: 50,
                ATTR_MODE: humidifier.MODE_AUTO,
            },
        ),
        BASIC_CONFIG,
    )

    attribs = trt.sync_attributes()
    assert attribs == {
        "availableModes": [
            {
                "name": "mode",
                "name_values": [{"name_synonym": ["mode"], "lang": "en"}],
                "settings": [
                    {
                        "setting_name": "normal",
                        "setting_values": [
                            {"setting_synonym": ["normal"], "lang": "en"}
                        ],
                    },
                    {
                        "setting_name": "auto",
                        "setting_values": [{"setting_synonym": ["auto"], "lang": "en"}],
                    },
                    {
                        "setting_name": "away",
                        "setting_values": [{"setting_synonym": ["away"], "lang": "en"}],
                    },
                ],
                "ordered": False,
            },
        ]
    }

    assert trt.query_attributes() == {
        "currentModeSettings": {"mode": "auto"},
        "on": False,
    }

    assert trt.can_execute(
        trait.COMMAND_MODES, params={"updateModeSettings": {"mode": "away"}}
    )

    calls = async_mock_service(hass, humidifier.DOMAIN, humidifier.SERVICE_SET_MODE)
    await trt.execute(
        trait.COMMAND_MODES,
        BASIC_DATA,
        {"updateModeSettings": {"mode": "away"}},
        {},
    )

    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": "humidifier.humidifier",
        "mode": "away",
    }


async def test_sound_modes(hass: HomeAssistant) -> None:
    """Test Mode trait."""
    assert helpers.get_google_type(media_player.DOMAIN, None) is not None
    assert trait.ModesTrait.supported(
        media_player.DOMAIN,
        MediaPlayerEntityFeature.SELECT_SOUND_MODE,
        None,
        None,
    )

    trt = trait.ModesTrait(
        hass,
        State(
            "media_player.living_room",
            media_player.STATE_PLAYING,
            attributes={
                media_player.ATTR_SOUND_MODE_LIST: ["stereo", "prologic"],
                media_player.ATTR_SOUND_MODE: "stereo",
            },
        ),
        BASIC_CONFIG,
    )

    attribs = trt.sync_attributes()
    assert attribs == {
        "availableModes": [
            {
                "name": "sound mode",
                "name_values": [
                    {"name_synonym": ["sound mode", "effects"], "lang": "en"}
                ],
                "settings": [
                    {
                        "setting_name": "stereo",
                        "setting_values": [
                            {"setting_synonym": ["stereo"], "lang": "en"}
                        ],
                    },
                    {
                        "setting_name": "prologic",
                        "setting_values": [
                            {"setting_synonym": ["prologic"], "lang": "en"}
                        ],
                    },
                ],
                "ordered": False,
            }
        ]
    }

    assert trt.query_attributes() == {
        "currentModeSettings": {"sound mode": "stereo"},
        "on": True,
    }

    assert trt.can_execute(
        trait.COMMAND_MODES,
        params={"updateModeSettings": {"sound mode": "stereo"}},
    )

    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_SELECT_SOUND_MODE
    )
    await trt.execute(
        trait.COMMAND_MODES,
        BASIC_DATA,
        {"updateModeSettings": {"sound mode": "stereo"}},
        {},
    )

    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": "media_player.living_room",
        "sound_mode": "stereo",
    }


async def test_preset_modes(hass: HomeAssistant) -> None:
    """Test Mode trait for fan preset modes."""
    assert helpers.get_google_type(fan.DOMAIN, None) is not None
    assert trait.ModesTrait.supported(
        fan.DOMAIN, FanEntityFeature.PRESET_MODE, None, None
    )

    trt = trait.ModesTrait(
        hass,
        State(
            "fan.living_room",
            STATE_ON,
            attributes={
                fan.ATTR_PRESET_MODES: ["auto", "whoosh"],
                fan.ATTR_PRESET_MODE: "auto",
                ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE,
            },
        ),
        BASIC_CONFIG,
    )

    attribs = trt.sync_attributes()
    assert attribs == {
        "availableModes": [
            {
                "name": "preset mode",
                "name_values": [
                    {"name_synonym": ["preset mode", "mode", "preset"], "lang": "en"}
                ],
                "settings": [
                    {
                        "setting_name": "auto",
                        "setting_values": [{"setting_synonym": ["auto"], "lang": "en"}],
                    },
                    {
                        "setting_name": "whoosh",
                        "setting_values": [
                            {"setting_synonym": ["whoosh"], "lang": "en"}
                        ],
                    },
                ],
                "ordered": False,
            }
        ]
    }

    assert trt.query_attributes() == {
        "currentModeSettings": {"preset mode": "auto"},
        "on": True,
    }

    assert trt.can_execute(
        trait.COMMAND_MODES,
        params={"updateModeSettings": {"preset mode": "auto"}},
    )

    calls = async_mock_service(hass, fan.DOMAIN, fan.SERVICE_SET_PRESET_MODE)
    await trt.execute(
        trait.COMMAND_MODES,
        BASIC_DATA,
        {"updateModeSettings": {"preset mode": "auto"}},
        {},
    )

    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": "fan.living_room",
        "preset_mode": "auto",
    }


async def test_traits_unknown_domains(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test Mode trait for unsupported domain."""
    trt = trait.ModesTrait(
        hass,
        State(
            "switch.living_room",
            STATE_ON,
        ),
        BASIC_CONFIG,
    )

    assert trt.supported("not_supported_domain", False, None, None) is False
    await trt.execute(
        trait.COMMAND_MODES,
        BASIC_DATA,
        {"updateModeSettings": {}},
        {},
    )
    assert "Received an Options command for unrecognised domain" in caplog.text
    caplog.clear()


async def test_openclose_cover(hass: HomeAssistant) -> None:
    """Test OpenClose trait support for cover domain."""
    assert helpers.get_google_type(cover.DOMAIN, None) is not None
    assert trait.OpenCloseTrait.supported(
        cover.DOMAIN, CoverEntityFeature.SET_POSITION, None, None
    )

    trt = trait.OpenCloseTrait(
        hass,
        State(
            "cover.bla",
            cover.STATE_OPEN,
            {
                cover.ATTR_CURRENT_POSITION: 75,
                ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {"openPercent": 75}

    calls_set = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_SET_COVER_POSITION)
    calls_open = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_OPEN_COVER)

    await trt.execute(trait.COMMAND_OPENCLOSE, BASIC_DATA, {"openPercent": 50}, {})
    await trt.execute(
        trait.COMMAND_OPENCLOSE_RELATIVE, BASIC_DATA, {"openRelativePercent": 50}, {}
    )
    assert len(calls_set) == 1
    assert calls_set[0].data == {ATTR_ENTITY_ID: "cover.bla", cover.ATTR_POSITION: 50}

    assert len(calls_open) == 1
    assert calls_open[0].data == {ATTR_ENTITY_ID: "cover.bla"}


async def test_openclose_cover_unknown_state(hass: HomeAssistant) -> None:
    """Test OpenClose trait support for cover domain with unknown state."""
    assert helpers.get_google_type(cover.DOMAIN, None) is not None
    assert trait.OpenCloseTrait.supported(
        cover.DOMAIN, CoverEntityFeature.SET_POSITION, None, None
    )

    # No state
    trt = trait.OpenCloseTrait(
        hass,
        State(
            "cover.bla",
            STATE_UNKNOWN,
            {ATTR_SUPPORTED_FEATURES: CoverEntityFeature.OPEN},
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {"discreteOnlyOpenClose": True}

    with pytest.raises(helpers.SmartHomeError):
        trt.query_attributes()

    calls = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_OPEN_COVER)
    await trt.execute(trait.COMMAND_OPENCLOSE, BASIC_DATA, {"openPercent": 100}, {})
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "cover.bla"}

    with pytest.raises(helpers.SmartHomeError):
        trt.query_attributes()


async def test_openclose_cover_assumed_state(hass: HomeAssistant) -> None:
    """Test OpenClose trait support for cover domain."""
    assert helpers.get_google_type(cover.DOMAIN, None) is not None
    assert trait.OpenCloseTrait.supported(
        cover.DOMAIN, CoverEntityFeature.SET_POSITION, None, None
    )

    trt = trait.OpenCloseTrait(
        hass,
        State(
            "cover.bla",
            cover.STATE_OPEN,
            {
                ATTR_ASSUMED_STATE: True,
                ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {"commandOnlyOpenClose": True}

    assert trt.query_attributes() == {}

    calls = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_SET_COVER_POSITION)
    await trt.execute(trait.COMMAND_OPENCLOSE, BASIC_DATA, {"openPercent": 40}, {})
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "cover.bla", cover.ATTR_POSITION: 40}


async def test_openclose_cover_query_only(hass: HomeAssistant) -> None:
    """Test OpenClose trait support for cover domain."""
    assert helpers.get_google_type(cover.DOMAIN, None) is not None
    assert trait.OpenCloseTrait.supported(cover.DOMAIN, 0, None, None)

    state = State(
        "cover.bla",
        cover.STATE_OPEN,
    )

    trt = trait.OpenCloseTrait(
        hass,
        state,
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "discreteOnlyOpenClose": True,
        "queryOnlyOpenClose": True,
    }
    assert trt.query_attributes() == {"openPercent": 100}


async def test_openclose_cover_no_position(hass: HomeAssistant) -> None:
    """Test OpenClose trait support for cover domain."""
    assert helpers.get_google_type(cover.DOMAIN, None) is not None
    assert trait.OpenCloseTrait.supported(
        cover.DOMAIN,
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
        None,
        None,
    )

    state = State(
        "cover.bla",
        cover.STATE_OPEN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
        },
    )

    trt = trait.OpenCloseTrait(
        hass,
        state,
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {"discreteOnlyOpenClose": True}
    assert trt.query_attributes() == {"openPercent": 100}

    state.state = cover.STATE_CLOSED

    assert trt.sync_attributes() == {"discreteOnlyOpenClose": True}
    assert trt.query_attributes() == {"openPercent": 0}

    calls = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_CLOSE_COVER)
    await trt.execute(trait.COMMAND_OPENCLOSE, BASIC_DATA, {"openPercent": 0}, {})
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "cover.bla"}

    calls = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_OPEN_COVER)
    await trt.execute(trait.COMMAND_OPENCLOSE, BASIC_DATA, {"openPercent": 100}, {})
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "cover.bla"}

    with pytest.raises(
        SmartHomeError, match=r"Current position not know for relative command"
    ):
        await trt.execute(
            trait.COMMAND_OPENCLOSE_RELATIVE,
            BASIC_DATA,
            {"openRelativePercent": 100},
            {},
        )

    with pytest.raises(SmartHomeError, match=r"No support for partial open close"):
        await trt.execute(trait.COMMAND_OPENCLOSE, BASIC_DATA, {"openPercent": 50}, {})


@pytest.mark.parametrize(
    "device_class",
    (
        cover.CoverDeviceClass.DOOR,
        cover.CoverDeviceClass.GARAGE,
        cover.CoverDeviceClass.GATE,
    ),
)
async def test_openclose_cover_secure(hass: HomeAssistant, device_class) -> None:
    """Test OpenClose trait support for cover domain."""
    assert helpers.get_google_type(cover.DOMAIN, device_class) is not None
    assert trait.OpenCloseTrait.supported(
        cover.DOMAIN, CoverEntityFeature.SET_POSITION, device_class, None
    )
    assert trait.OpenCloseTrait.might_2fa(
        cover.DOMAIN, CoverEntityFeature.SET_POSITION, device_class
    )

    trt = trait.OpenCloseTrait(
        hass,
        State(
            "cover.bla",
            cover.STATE_OPEN,
            {
                ATTR_DEVICE_CLASS: device_class,
                ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
                cover.ATTR_CURRENT_POSITION: 75,
            },
        ),
        PIN_CONFIG,
    )

    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {"openPercent": 75}

    calls = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_SET_COVER_POSITION)
    calls_close = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_CLOSE_COVER)

    # No challenge data
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(trait.COMMAND_OPENCLOSE, PIN_DATA, {"openPercent": 50}, {})
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_PIN_NEEDED

    # invalid pin
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(
            trait.COMMAND_OPENCLOSE, PIN_DATA, {"openPercent": 50}, {"pin": "9999"}
        )
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_FAILED_PIN_NEEDED

    await trt.execute(
        trait.COMMAND_OPENCLOSE, PIN_DATA, {"openPercent": 50}, {"pin": "1234"}
    )
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "cover.bla", cover.ATTR_POSITION: 50}

    # no challenge on close
    await trt.execute(trait.COMMAND_OPENCLOSE, PIN_DATA, {"openPercent": 0}, {})
    assert len(calls_close) == 1
    assert calls_close[0].data == {ATTR_ENTITY_ID: "cover.bla"}


@pytest.mark.parametrize(
    "device_class",
    (
        binary_sensor.BinarySensorDeviceClass.DOOR,
        binary_sensor.BinarySensorDeviceClass.GARAGE_DOOR,
        binary_sensor.BinarySensorDeviceClass.LOCK,
        binary_sensor.BinarySensorDeviceClass.OPENING,
        binary_sensor.BinarySensorDeviceClass.WINDOW,
    ),
)
async def test_openclose_binary_sensor(hass: HomeAssistant, device_class) -> None:
    """Test OpenClose trait support for binary_sensor domain."""
    assert helpers.get_google_type(binary_sensor.DOMAIN, device_class) is not None
    assert trait.OpenCloseTrait.supported(binary_sensor.DOMAIN, 0, device_class, None)

    trt = trait.OpenCloseTrait(
        hass,
        State("binary_sensor.test", STATE_ON, {ATTR_DEVICE_CLASS: device_class}),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "queryOnlyOpenClose": True,
        "discreteOnlyOpenClose": True,
    }

    assert trt.query_attributes() == {"openPercent": 100}

    trt = trait.OpenCloseTrait(
        hass,
        State("binary_sensor.test", STATE_OFF, {ATTR_DEVICE_CLASS: device_class}),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "queryOnlyOpenClose": True,
        "discreteOnlyOpenClose": True,
    }

    assert trt.query_attributes() == {"openPercent": 0}


async def test_volume_media_player(hass: HomeAssistant) -> None:
    """Test volume trait support for media player domain."""
    assert helpers.get_google_type(media_player.DOMAIN, None) is not None
    assert trait.VolumeTrait.supported(
        media_player.DOMAIN,
        MediaPlayerEntityFeature.VOLUME_SET,
        None,
        None,
    )

    trt = trait.VolumeTrait(
        hass,
        State(
            "media_player.bla",
            media_player.STATE_PLAYING,
            {
                ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.VOLUME_SET,
                media_player.ATTR_MEDIA_VOLUME_LEVEL: 0.3,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "volumeMaxLevel": 100,
        "levelStepSize": 10,
        "volumeCanMuteAndUnmute": False,
        "commandOnlyVolume": False,
    }

    assert trt.query_attributes() == {"currentVolume": 30}

    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_SET
    )
    await trt.execute(trait.COMMAND_SET_VOLUME, BASIC_DATA, {"volumeLevel": 60}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "media_player.bla",
        media_player.ATTR_MEDIA_VOLUME_LEVEL: 0.6,
    }

    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_SET
    )
    await trt.execute(
        trait.COMMAND_VOLUME_RELATIVE, BASIC_DATA, {"relativeSteps": 10}, {}
    )
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "media_player.bla",
        media_player.ATTR_MEDIA_VOLUME_LEVEL: 0.4,
    }


async def test_volume_media_player_relative(hass: HomeAssistant) -> None:
    """Test volume trait support for relative-volume-only media players."""
    assert trait.VolumeTrait.supported(
        media_player.DOMAIN,
        MediaPlayerEntityFeature.VOLUME_STEP,
        None,
        None,
    )
    trt = trait.VolumeTrait(
        hass,
        State(
            "media_player.bla",
            media_player.STATE_PLAYING,
            {
                ATTR_ASSUMED_STATE: True,
                ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.VOLUME_STEP,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "volumeMaxLevel": 100,
        "levelStepSize": 10,
        "volumeCanMuteAndUnmute": False,
        "commandOnlyVolume": True,
    }

    assert trt.query_attributes() == {}

    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_UP
    )

    await trt.execute(
        trait.COMMAND_VOLUME_RELATIVE,
        BASIC_DATA,
        {"relativeSteps": 10},
        {},
    )
    assert len(calls) == 10
    for call in calls:
        assert call.data == {
            ATTR_ENTITY_ID: "media_player.bla",
        }

    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_DOWN
    )
    await trt.execute(
        trait.COMMAND_VOLUME_RELATIVE,
        BASIC_DATA,
        {"relativeSteps": -10},
        {},
    )
    assert len(calls) == 10
    for call in calls:
        assert call.data == {
            ATTR_ENTITY_ID: "media_player.bla",
        }

    with pytest.raises(SmartHomeError):
        await trt.execute(trait.COMMAND_SET_VOLUME, BASIC_DATA, {"volumeLevel": 42}, {})

    with pytest.raises(SmartHomeError):
        await trt.execute(trait.COMMAND_MUTE, BASIC_DATA, {"mute": True}, {})


async def test_media_player_mute(hass: HomeAssistant) -> None:
    """Test volume trait support for muting."""
    assert trait.VolumeTrait.supported(
        media_player.DOMAIN,
        MediaPlayerEntityFeature.VOLUME_STEP | MediaPlayerEntityFeature.VOLUME_MUTE,
        None,
        None,
    )
    trt = trait.VolumeTrait(
        hass,
        State(
            "media_player.bla",
            media_player.STATE_PLAYING,
            {
                ATTR_SUPPORTED_FEATURES: (
                    MediaPlayerEntityFeature.VOLUME_STEP
                    | MediaPlayerEntityFeature.VOLUME_MUTE
                ),
                media_player.ATTR_MEDIA_VOLUME_MUTED: False,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "volumeMaxLevel": 100,
        "levelStepSize": 10,
        "volumeCanMuteAndUnmute": True,
        "commandOnlyVolume": False,
    }
    assert trt.query_attributes() == {"isMuted": False}

    mute_calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_MUTE
    )
    await trt.execute(
        trait.COMMAND_MUTE,
        BASIC_DATA,
        {"mute": True},
        {},
    )
    assert len(mute_calls) == 1
    assert mute_calls[0].data == {
        ATTR_ENTITY_ID: "media_player.bla",
        media_player.ATTR_MEDIA_VOLUME_MUTED: True,
    }

    unmute_calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_MUTE
    )
    await trt.execute(
        trait.COMMAND_MUTE,
        BASIC_DATA,
        {"mute": False},
        {},
    )
    assert len(unmute_calls) == 1
    assert unmute_calls[0].data == {
        ATTR_ENTITY_ID: "media_player.bla",
        media_player.ATTR_MEDIA_VOLUME_MUTED: False,
    }


async def test_temperature_control_sensor(hass: HomeAssistant) -> None:
    """Test TemperatureControl trait support for temperature sensor."""
    assert (
        helpers.get_google_type(sensor.DOMAIN, sensor.SensorDeviceClass.TEMPERATURE)
        is not None
    )
    assert not trait.TemperatureControlTrait.supported(
        sensor.DOMAIN, 0, sensor.SensorDeviceClass.HUMIDITY, None
    )
    assert trait.TemperatureControlTrait.supported(
        sensor.DOMAIN, 0, sensor.SensorDeviceClass.TEMPERATURE, None
    )


@pytest.mark.parametrize(
    ("unit_in", "unit_out", "state", "ambient"),
    [
        (UnitOfTemperature.FAHRENHEIT, "F", "70", 21.1),
        (UnitOfTemperature.CELSIUS, "C", "21.1", 21.1),
        (UnitOfTemperature.FAHRENHEIT, "F", "unavailable", None),
        (UnitOfTemperature.FAHRENHEIT, "F", "unknown", None),
    ],
)
async def test_temperature_control_sensor_data(
    hass: HomeAssistant, unit_in, unit_out, state, ambient
) -> None:
    """Test TemperatureControl trait support for temperature sensor."""
    hass.config.units.temperature_unit = unit_in

    trt = trait.TemperatureControlTrait(
        hass,
        State(
            "sensor.test",
            state,
            {ATTR_DEVICE_CLASS: sensor.SensorDeviceClass.TEMPERATURE},
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "queryOnlyTemperatureControl": True,
        "temperatureUnitForUX": unit_out,
        "temperatureRange": {"maxThresholdCelsius": 100, "minThresholdCelsius": -100},
    }

    if ambient:
        assert trt.query_attributes() == {
            "temperatureAmbientCelsius": ambient,
            "temperatureSetpointCelsius": ambient,
        }
    else:
        assert trt.query_attributes() == {}
    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS


async def test_humidity_setting_sensor(hass: HomeAssistant) -> None:
    """Test HumiditySetting trait support for humidity sensor."""
    assert (
        helpers.get_google_type(sensor.DOMAIN, sensor.SensorDeviceClass.HUMIDITY)
        is not None
    )
    assert not trait.HumiditySettingTrait.supported(
        sensor.DOMAIN, 0, sensor.SensorDeviceClass.TEMPERATURE, None
    )
    assert trait.HumiditySettingTrait.supported(
        sensor.DOMAIN, 0, sensor.SensorDeviceClass.HUMIDITY, None
    )


@pytest.mark.parametrize(
    ("state", "ambient"), [("70", 70), ("unavailable", None), ("unknown", None)]
)
async def test_humidity_setting_sensor_data(
    hass: HomeAssistant, state, ambient
) -> None:
    """Test HumiditySetting trait support for humidity sensor."""
    trt = trait.HumiditySettingTrait(
        hass,
        State(
            "sensor.test", state, {ATTR_DEVICE_CLASS: sensor.SensorDeviceClass.HUMIDITY}
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {"queryOnlyHumiditySetting": True}
    if ambient:
        assert trt.query_attributes() == {"humidityAmbientPercent": ambient}
    else:
        assert trt.query_attributes() == {}

    with pytest.raises(helpers.SmartHomeError) as err:
        await trt.execute(trait.COMMAND_ONOFF, BASIC_DATA, {"on": False}, {})
    assert err.value.code == const.ERR_NOT_SUPPORTED


async def test_transport_control(hass: HomeAssistant) -> None:
    """Test the TransportControlTrait."""
    assert helpers.get_google_type(media_player.DOMAIN, None) is not None

    for feature in trait.MEDIA_COMMAND_SUPPORT_MAPPING.values():
        assert trait.TransportControlTrait.supported(
            media_player.DOMAIN, feature, None, None
        )

    now = datetime(2020, 1, 1)

    trt = trait.TransportControlTrait(
        hass,
        State(
            "media_player.bla",
            media_player.STATE_PLAYING,
            {
                media_player.ATTR_MEDIA_POSITION: 100,
                media_player.ATTR_MEDIA_DURATION: 200,
                media_player.ATTR_MEDIA_POSITION_UPDATED_AT: now
                - timedelta(seconds=10),
                media_player.ATTR_MEDIA_VOLUME_LEVEL: 0.5,
                ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.STOP,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "transportControlSupportedCommands": ["RESUME", "STOP"]
    }
    assert trt.query_attributes() == {}

    # COMMAND_MEDIA_SEEK_RELATIVE
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_SEEK
    )

    # Patch to avoid time ticking over during the command failing the test
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await trt.execute(
            trait.COMMAND_MEDIA_SEEK_RELATIVE,
            BASIC_DATA,
            {"relativePositionMs": 10000},
            {},
        )
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "media_player.bla",
        # 100s (current position) + 10s (from command) + 10s (from updated_at)
        media_player.ATTR_MEDIA_SEEK_POSITION: 120,
    }

    # COMMAND_MEDIA_SEEK_TO_POSITION
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_SEEK
    )
    await trt.execute(
        trait.COMMAND_MEDIA_SEEK_TO_POSITION, BASIC_DATA, {"absPositionMs": 50000}, {}
    )
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "media_player.bla",
        media_player.ATTR_MEDIA_SEEK_POSITION: 50,
    }

    # COMMAND_MEDIA_NEXT
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_NEXT_TRACK
    )
    await trt.execute(trait.COMMAND_MEDIA_NEXT, BASIC_DATA, {}, {})
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "media_player.bla"}

    # COMMAND_MEDIA_PAUSE
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_PAUSE
    )
    await trt.execute(trait.COMMAND_MEDIA_PAUSE, BASIC_DATA, {}, {})
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "media_player.bla"}

    # COMMAND_MEDIA_PREVIOUS
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_PREVIOUS_TRACK
    )
    await trt.execute(trait.COMMAND_MEDIA_PREVIOUS, BASIC_DATA, {}, {})
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "media_player.bla"}

    # COMMAND_MEDIA_RESUME
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_PLAY
    )
    await trt.execute(trait.COMMAND_MEDIA_RESUME, BASIC_DATA, {}, {})
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "media_player.bla"}

    # COMMAND_MEDIA_SHUFFLE
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_SHUFFLE_SET
    )
    await trt.execute(trait.COMMAND_MEDIA_SHUFFLE, BASIC_DATA, {}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "media_player.bla",
        media_player.ATTR_MEDIA_SHUFFLE: True,
    }

    # COMMAND_MEDIA_STOP
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_STOP
    )
    await trt.execute(trait.COMMAND_MEDIA_STOP, BASIC_DATA, {}, {})
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: "media_player.bla"}


@pytest.mark.parametrize(
    "state",
    (
        STATE_OFF,
        STATE_IDLE,
        STATE_PLAYING,
        STATE_ON,
        STATE_PAUSED,
        STATE_STANDBY,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ),
)
async def test_media_state(hass: HomeAssistant, state) -> None:
    """Test the MediaStateTrait."""
    assert helpers.get_google_type(media_player.DOMAIN, None) is not None

    assert trait.TransportControlTrait.supported(
        media_player.DOMAIN, MediaPlayerEntityFeature.PLAY, None, None
    )

    trt = trait.MediaStateTrait(
        hass,
        State(
            "media_player.bla",
            state,
            {
                media_player.ATTR_MEDIA_POSITION: 100,
                media_player.ATTR_MEDIA_DURATION: 200,
                media_player.ATTR_MEDIA_VOLUME_LEVEL: 0.5,
                ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.STOP,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {
        "supportActivityState": True,
        "supportPlaybackState": True,
    }
    assert trt.query_attributes() == {
        "activityState": trt.activity_lookup.get(state),
        "playbackState": trt.playback_lookup.get(state),
    }


async def test_channel(hass: HomeAssistant) -> None:
    """Test Channel trait support."""
    assert helpers.get_google_type(media_player.DOMAIN, None) is not None
    assert trait.ChannelTrait.supported(
        media_player.DOMAIN,
        MediaPlayerEntityFeature.PLAY_MEDIA,
        media_player.MediaPlayerDeviceClass.TV,
        None,
    )
    assert (
        trait.ChannelTrait.supported(
            media_player.DOMAIN,
            MediaPlayerEntityFeature.PLAY_MEDIA,
            None,
            None,
        )
        is False
    )
    assert trait.ChannelTrait.supported(media_player.DOMAIN, 0, None, None) is False

    trt = trait.ChannelTrait(hass, State("media_player.demo", STATE_ON), BASIC_CONFIG)

    assert trt.sync_attributes() == {
        "availableChannels": [],
        "commandOnlyChannels": True,
    }
    assert trt.query_attributes() == {}

    media_player_calls = async_mock_service(
        hass, media_player.DOMAIN, SERVICE_PLAY_MEDIA
    )
    await trt.execute(
        trait.COMMAND_SELECT_CHANNEL, BASIC_DATA, {"channelNumber": "1"}, {}
    )
    assert len(media_player_calls) == 1
    assert media_player_calls[0].data == {
        ATTR_ENTITY_ID: "media_player.demo",
        media_player.ATTR_MEDIA_CONTENT_ID: "1",
        media_player.ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
    }

    with pytest.raises(SmartHomeError, match="Channel is not available"):
        await trt.execute(
            trait.COMMAND_SELECT_CHANNEL, BASIC_DATA, {"channelCode": "Channel 3"}, {}
        )
    assert len(media_player_calls) == 1

    with pytest.raises(SmartHomeError, match="Unsupported command"):
        await trt.execute("Unknown command", BASIC_DATA, {"channelNumber": "1"}, {})
    assert len(media_player_calls) == 1


async def test_air_quality_description_for_aqi(hass: HomeAssistant) -> None:
    """Test air quality description for a given AQI value."""
    trt = trait.SensorStateTrait(
        hass,
        State(
            "sensor.test",
            100.0,
            {
                "device_class": sensor.SensorDeviceClass.AQI,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt._air_quality_description_for_aqi("0") == "healthy"
    assert trt._air_quality_description_for_aqi("75") == "moderate"
    assert (
        trt._air_quality_description_for_aqi("125") == "unhealthy for sensitive groups"
    )
    assert trt._air_quality_description_for_aqi("175") == "unhealthy"
    assert trt._air_quality_description_for_aqi("250") == "very unhealthy"
    assert trt._air_quality_description_for_aqi("350") == "hazardous"
    assert trt._air_quality_description_for_aqi("-1") == "unknown"
    assert trt._air_quality_description_for_aqi("non-numeric") == "unknown"


async def test_null_device_class(hass: HomeAssistant) -> None:
    """Test handling a null device_class in sync_attributes and query_attributes."""
    trt = trait.SensorStateTrait(
        hass,
        State(
            "sensor.test",
            100.0,
            {
                "device_class": None,
            },
        ),
        BASIC_CONFIG,
    )

    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {}


async def test_sensorstate(hass: HomeAssistant) -> None:
    """Test SensorState trait support for sensor domain."""
    sensor_types = {
        sensor.SensorDeviceClass.AQI: ("AirQuality", "AQI"),
        sensor.SensorDeviceClass.CO: ("CarbonMonoxideLevel", "PARTS_PER_MILLION"),
        sensor.SensorDeviceClass.CO2: ("CarbonDioxideLevel", "PARTS_PER_MILLION"),
        sensor.SensorDeviceClass.PM25: ("PM2.5", "MICROGRAMS_PER_CUBIC_METER"),
        sensor.SensorDeviceClass.PM10: ("PM10", "MICROGRAMS_PER_CUBIC_METER"),
        sensor.SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS: (
            "VolatileOrganicCompounds",
            "PARTS_PER_MILLION",
        ),
    }

    for sensor_type in sensor_types:
        assert helpers.get_google_type(sensor.DOMAIN, None) is not None
        assert trait.SensorStateTrait.supported(sensor.DOMAIN, None, sensor_type, None)

        trt = trait.SensorStateTrait(
            hass,
            State(
                "sensor.test",
                100.0,
                {
                    "device_class": sensor_type,
                },
            ),
            BASIC_CONFIG,
        )

        name = sensor_types[sensor_type][0]
        unit = sensor_types[sensor_type][1]

        if sensor_type == sensor.SensorDeviceClass.AQI:
            assert trt.sync_attributes() == {
                "sensorStatesSupported": [
                    {
                        "name": name,
                        "numericCapabilities": {"rawValueUnit": unit},
                        "descriptiveCapabilities": {
                            "availableStates": [
                                "healthy",
                                "moderate",
                                "unhealthy for sensitive groups",
                                "unhealthy",
                                "very unhealthy",
                                "hazardous",
                                "unknown",
                            ],
                        },
                    }
                ]
            }
        else:
            assert trt.sync_attributes() == {
                "sensorStatesSupported": [
                    {
                        "name": name,
                        "numericCapabilities": {"rawValueUnit": unit},
                    }
                ]
            }

        if sensor_type == sensor.SensorDeviceClass.AQI:
            assert trt.query_attributes() == {
                "currentSensorStateData": [
                    {
                        "name": name,
                        "currentSensorState": trt._air_quality_description_for_aqi(
                            trt.state.state
                        ),
                        "rawValue": trt.state.state,
                    },
                ]
            }
        else:
            assert trt.query_attributes() == {
                "currentSensorStateData": [{"name": name, "rawValue": trt.state.state}]
            }

    assert helpers.get_google_type(sensor.DOMAIN, None) is not None
    assert (
        trait.SensorStateTrait.supported(
            sensor.DOMAIN, None, sensor.SensorDeviceClass.MONETARY, None
        )
        is False
    )
