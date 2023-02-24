"""Test Google Smart Home."""
import asyncio
from unittest.mock import ANY, call, patch

import pytest
from pytest_unordered import unordered

from homeassistant.components import camera
from homeassistant.components.climate import ATTR_MAX_TEMP, ATTR_MIN_TEMP, HVACMode
from homeassistant.components.demo.binary_sensor import DemoBinarySensor
from homeassistant.components.demo.cover import DemoCover
from homeassistant.components.demo.light import LIGHT_EFFECT_LIST, DemoLight
from homeassistant.components.demo.media_player import AbstractDemoPlayer
from homeassistant.components.demo.switch import DemoSwitch
from homeassistant.components.google_assistant import (
    EVENT_COMMAND_RECEIVED,
    EVENT_QUERY_RECEIVED,
    EVENT_SYNC_RECEIVED,
    const,
    smart_home as sh,
    trait,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature, __version__
from homeassistant.core import EVENT_CALL_SERVICE, HomeAssistant, State
from homeassistant.helpers import device_registry, entity_platform
from homeassistant.setup import async_setup_component

from . import BASIC_CONFIG, MockConfig

from tests.common import (
    async_capture_events,
    mock_area_registry,
    mock_device_registry,
    mock_registry,
)

REQ_ID = "ff36a3cc-ec34-11e6-b1a0-64510650abcf"


@pytest.fixture
def registries(hass):
    """Registry mock setup."""
    from types import SimpleNamespace

    ret = SimpleNamespace()
    ret.entity = mock_registry(hass)
    ret.device = mock_device_registry(hass)
    ret.area = mock_area_registry(hass)
    return ret


async def test_async_handle_message(hass: HomeAssistant) -> None:
    """Test the async handle message method."""
    config = MockConfig(
        should_expose=lambda state: state.entity_id != "light.not_expose",
        entity_config={
            "light.demo_light": {
                const.CONF_ROOM_HINT: "Living Room",
                const.CONF_ALIASES: ["Hello", "World"],
            }
        },
    )

    result = await sh.async_handle_message(
        hass,
        config,
        "test-agent",
        {
            "requestId": REQ_ID,
            "inputs": [
                {"intent": "action.devices.SYNC"},
                {"intent": "action.devices.SYNC"},
            ],
        },
        const.SOURCE_CLOUD,
    )
    assert result == {
        "requestId": REQ_ID,
        "payload": {"errorCode": const.ERR_PROTOCOL_ERROR},
    }

    await hass.async_block_till_done()

    result = await sh.async_handle_message(
        hass,
        config,
        "test-agent",
        {
            "requestId": REQ_ID,
            "inputs": [
                {"intent": "action.devices.DOES_NOT_EXIST"},
            ],
        },
        const.SOURCE_CLOUD,
    )
    assert result == {
        "requestId": REQ_ID,
        "payload": {"errorCode": const.ERR_PROTOCOL_ERROR},
    }

    await hass.async_block_till_done()


async def test_sync_message(hass: HomeAssistant, registries) -> None:
    """Test a sync message."""
    entity = registries.entity.async_get_or_create(
        "light",
        "test",
        "unique-demo-light",
        suggested_object_id="demo_light",
    )
    registries.entity.async_update_entity(
        entity.entity_id,
        aliases={"Stay", "Healthy"},
    )

    light = DemoLight(
        "unique-demo-light",
        "Demo Light",
        state=False,
        hs_color=(180, 75),
        effect_list=LIGHT_EFFECT_LIST,
        effect=LIGHT_EFFECT_LIST[0],
    )
    light.hass = hass
    light.entity_id = "light.demo_light"
    await light.async_update_ha_state()

    # This should not show up in the sync request
    hass.states.async_set("sensor.no_match", "something")

    # Excluded via config
    hass.states.async_set("light.not_expose", "on")

    config = MockConfig(
        should_expose=lambda state: state.entity_id != "light.not_expose",
        entity_config={
            "light.demo_light": {
                const.CONF_ROOM_HINT: "Living Room",
                const.CONF_ALIASES: ["Hello", "World"],
            }
        },
    )

    events = async_capture_events(hass, EVENT_SYNC_RECEIVED)

    result = await sh.async_handle_message(
        hass,
        config,
        "test-agent",
        {"requestId": REQ_ID, "inputs": [{"intent": "action.devices.SYNC"}]},
        const.SOURCE_CLOUD,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "agentUserId": "test-agent",
            "devices": [
                {
                    "id": "light.demo_light",
                    "name": {
                        "name": "Demo Light",
                        "nicknames": unordered(
                            [
                                "Demo Light",
                                "Hello",
                                "World",
                                "Stay",
                                "Healthy",
                            ]
                        ),
                    },
                    "traits": [
                        trait.TRAIT_BRIGHTNESS,
                        trait.TRAIT_ONOFF,
                        trait.TRAIT_COLOR_SETTING,
                        trait.TRAIT_MODES,
                    ],
                    "type": const.TYPE_LIGHT,
                    "willReportState": False,
                    "attributes": {
                        "availableModes": [
                            {
                                "name": "effect",
                                "name_values": [
                                    {"lang": "en", "name_synonym": ["effect"]}
                                ],
                                "ordered": False,
                                "settings": [
                                    {
                                        "setting_name": "rainbow",
                                        "setting_values": [
                                            {
                                                "lang": "en",
                                                "setting_synonym": ["rainbow"],
                                            }
                                        ],
                                    },
                                    {
                                        "setting_name": "none",
                                        "setting_values": [
                                            {
                                                "lang": "en",
                                                "setting_synonym": ["none"],
                                            }
                                        ],
                                    },
                                ],
                            }
                        ],
                        "colorModel": "hsv",
                        "colorTemperatureRange": {
                            "temperatureMinK": 2000,
                            "temperatureMaxK": 6535,
                        },
                    },
                    "roomHint": "Living Room",
                }
            ],
        },
    }
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == EVENT_SYNC_RECEIVED
    assert events[0].data == {"request_id": REQ_ID, "source": "cloud"}


@pytest.mark.parametrize("area_on_device", [True, False])
async def test_sync_in_area(area_on_device, hass: HomeAssistant, registries) -> None:
    """Test a sync message where room hint comes from area."""
    area = registries.area.async_create("Living Room")

    device = registries.device.async_get_or_create(
        config_entry_id="1234",
        manufacturer="Someone",
        model="Some model",
        sw_version="Some Version",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    registries.device.async_update_device(
        device.id, area_id=area.id if area_on_device else None
    )

    entity = registries.entity.async_get_or_create(
        "light",
        "test",
        "1235",
        suggested_object_id="demo_light",
        device_id=device.id,
    )
    entity = registries.entity.async_update_entity(
        entity.entity_id, area_id=area.id if not area_on_device else None
    )

    light = DemoLight(
        None,
        "Demo Light",
        state=False,
        hs_color=(180, 75),
        effect_list=LIGHT_EFFECT_LIST,
        effect=LIGHT_EFFECT_LIST[0],
    )
    light.hass = hass
    light.entity_id = entity.entity_id
    await light.async_update_ha_state()

    config = MockConfig(should_expose=lambda _: True, entity_config={})

    events = async_capture_events(hass, EVENT_SYNC_RECEIVED)

    result = await sh.async_handle_message(
        hass,
        config,
        "test-agent",
        {"requestId": REQ_ID, "inputs": [{"intent": "action.devices.SYNC"}]},
        const.SOURCE_CLOUD,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "agentUserId": "test-agent",
            "devices": [
                {
                    "id": "light.demo_light",
                    "name": {"name": "Demo Light"},
                    "traits": [
                        trait.TRAIT_BRIGHTNESS,
                        trait.TRAIT_ONOFF,
                        trait.TRAIT_COLOR_SETTING,
                        trait.TRAIT_MODES,
                    ],
                    "type": const.TYPE_LIGHT,
                    "willReportState": False,
                    "attributes": {
                        "availableModes": [
                            {
                                "name": "effect",
                                "name_values": [
                                    {"lang": "en", "name_synonym": ["effect"]}
                                ],
                                "ordered": False,
                                "settings": [
                                    {
                                        "setting_name": "rainbow",
                                        "setting_values": [
                                            {
                                                "lang": "en",
                                                "setting_synonym": ["rainbow"],
                                            }
                                        ],
                                    },
                                    {
                                        "setting_name": "none",
                                        "setting_values": [
                                            {"lang": "en", "setting_synonym": ["none"]}
                                        ],
                                    },
                                ],
                            }
                        ],
                        "colorModel": "hsv",
                        "colorTemperatureRange": {
                            "temperatureMinK": 2000,
                            "temperatureMaxK": 6535,
                        },
                    },
                    "deviceInfo": {
                        "manufacturer": "Someone",
                        "model": "Some model",
                        "swVersion": "Some Version",
                    },
                    "roomHint": "Living Room",
                }
            ],
        },
    }
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == EVENT_SYNC_RECEIVED
    assert events[0].data == {"request_id": REQ_ID, "source": "cloud"}


async def test_query_message(hass: HomeAssistant) -> None:
    """Test a sync message."""
    light = DemoLight(
        None,
        "Demo Light",
        state=False,
        hs_color=(180, 75),
        effect_list=LIGHT_EFFECT_LIST,
        effect=LIGHT_EFFECT_LIST[0],
    )
    light.hass = hass
    light.entity_id = "light.demo_light"
    await light.async_update_ha_state()

    light2 = DemoLight(
        None, "Another Light", state=True, hs_color=(180, 75), ct=400, brightness=78
    )
    light2.hass = hass
    light2.entity_id = "light.another_light"
    await light2.async_update_ha_state()

    light3 = DemoLight(None, "Color temp Light", state=True, ct=400, brightness=200)
    light3.hass = hass
    light3.entity_id = "light.color_temp_light"
    await light3.async_update_ha_state()

    events = async_capture_events(hass, EVENT_QUERY_RECEIVED)

    result = await sh.async_handle_message(
        hass,
        BASIC_CONFIG,
        "test-agent",
        {
            "requestId": REQ_ID,
            "inputs": [
                {
                    "intent": "action.devices.QUERY",
                    "payload": {
                        "devices": [
                            {"id": "light.demo_light"},
                            {"id": "light.another_light"},
                            {"id": "light.color_temp_light"},
                            {"id": "light.non_existing"},
                        ]
                    },
                }
            ],
        },
        const.SOURCE_CLOUD,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "devices": {
                "light.non_existing": {"online": False},
                "light.demo_light": {"on": False, "online": True},
                "light.another_light": {
                    "on": True,
                    "online": True,
                    "brightness": 31,
                    "color": {
                        "spectrumHsv": {
                            "hue": 180,
                            "saturation": 0.75,
                            "value": 0.3058823529411765,
                        },
                    },
                },
                "light.color_temp_light": {
                    "on": True,
                    "online": True,
                    "brightness": 78,
                    "color": {"temperatureK": 2500},
                },
            }
        },
    }

    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == EVENT_QUERY_RECEIVED
    assert events[0].data == {
        "request_id": REQ_ID,
        "entity_id": [
            "light.demo_light",
            "light.another_light",
            "light.color_temp_light",
            "light.non_existing",
        ],
        "source": "cloud",
    }


@pytest.mark.parametrize(
    ("report_state", "on", "brightness", "value"),
    [(False, True, 20, 0.2), (True, ANY, ANY, ANY)],
)
async def test_execute(
    hass: HomeAssistant, report_state, on, brightness, value
) -> None:
    """Test an execute command."""
    await async_setup_component(hass, "light", {"light": {"platform": "demo"}})
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.ceiling_lights"}, blocking=True
    )
    await hass.async_block_till_done()

    events = async_capture_events(hass, EVENT_COMMAND_RECEIVED)
    service_events = async_capture_events(hass, EVENT_CALL_SERVICE)

    with patch.object(
        hass.services, "async_call", wraps=hass.services.async_call
    ) as call_service_mock:
        result = await sh.async_handle_message(
            hass,
            MockConfig(should_report_state=report_state),
            None,
            {
                "requestId": REQ_ID,
                "inputs": [
                    {
                        "intent": "action.devices.EXECUTE",
                        "payload": {
                            "commands": [
                                {
                                    "devices": [
                                        {"id": "light.non_existing"},
                                        {"id": "light.ceiling_lights"},
                                        {"id": "light.kitchen_lights"},
                                    ],
                                    "execution": [
                                        {
                                            "command": "action.devices.commands.OnOff",
                                            "params": {"on": True},
                                        },
                                        {
                                            "command": "action.devices.commands.BrightnessAbsolute",
                                            "params": {"brightness": 20},
                                        },
                                    ],
                                }
                            ]
                        },
                    }
                ],
            },
            const.SOURCE_CLOUD,
        )
        assert call_service_mock.call_count == 4
        expected_calls = [
            call(
                "light",
                "turn_on",
                {"entity_id": "light.ceiling_lights"},
                blocking=not report_state,
                context=ANY,
            ),
            call(
                "light",
                "turn_on",
                {"entity_id": "light.kitchen_lights"},
                blocking=not report_state,
                context=ANY,
            ),
            call(
                "light",
                "turn_on",
                {"entity_id": "light.ceiling_lights", "brightness_pct": 20},
                blocking=not report_state,
                context=ANY,
            ),
            call(
                "light",
                "turn_on",
                {"entity_id": "light.kitchen_lights", "brightness_pct": 20},
                blocking=not report_state,
                context=ANY,
            ),
        ]
        call_service_mock.assert_has_awaits(expected_calls, any_order=True)
    await hass.async_block_till_done()

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "commands": [
                {
                    "ids": ["light.non_existing"],
                    "status": "ERROR",
                    "errorCode": "deviceOffline",
                },
                {
                    "ids": ["light.ceiling_lights"],
                    "status": "SUCCESS",
                    "states": {
                        "on": on,
                        "online": True,
                        "brightness": brightness,
                        "color": {"temperatureK": 2631},
                    },
                },
                {
                    "ids": ["light.kitchen_lights"],
                    "status": "SUCCESS",
                    "states": {
                        "on": True,
                        "online": True,
                        "brightness": brightness,
                        "color": {
                            "spectrumHsv": {
                                "hue": 345,
                                "saturation": 0.75,
                                "value": value,
                            },
                        },
                    },
                },
            ]
        },
    }

    assert len(events) == 1
    assert events[0].event_type == EVENT_COMMAND_RECEIVED
    assert events[0].data == {
        "request_id": REQ_ID,
        "entity_id": [
            "light.non_existing",
            "light.ceiling_lights",
            "light.kitchen_lights",
        ],
        "execution": [
            {
                "command": "action.devices.commands.OnOff",
                "params": {"on": True},
            },
            {
                "command": "action.devices.commands.BrightnessAbsolute",
                "params": {"brightness": 20},
            },
        ],
        "source": "cloud",
    }

    service_events = sorted(
        service_events, key=lambda ev: ev.data["service_data"]["entity_id"]
    )
    assert len(service_events) == 4
    assert service_events[0].data == {
        "domain": "light",
        "service": "turn_on",
        "service_data": {"entity_id": "light.ceiling_lights"},
    }
    assert service_events[1].data == {
        "domain": "light",
        "service": "turn_on",
        "service_data": {"brightness_pct": 20, "entity_id": "light.ceiling_lights"},
    }
    assert service_events[0].context == events[0].context
    assert service_events[1].context == events[0].context
    assert service_events[2].data == {
        "domain": "light",
        "service": "turn_on",
        "service_data": {"entity_id": "light.kitchen_lights"},
    }
    assert service_events[3].data == {
        "domain": "light",
        "service": "turn_on",
        "service_data": {"brightness_pct": 20, "entity_id": "light.kitchen_lights"},
    }
    assert service_events[2].context == events[0].context
    assert service_events[3].context == events[0].context


@pytest.mark.parametrize(
    ("report_state", "on", "brightness", "value"), [(False, False, ANY, ANY)]
)
async def test_execute_times_out(
    hass: HomeAssistant, report_state, on, brightness, value
) -> None:
    """Test an execute command which times out."""
    orig_execute_limit = sh.EXECUTE_LIMIT
    sh.EXECUTE_LIMIT = 0.02  # Decrease timeout to 20ms
    await async_setup_component(hass, "light", {"light": {"platform": "demo"}})
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.ceiling_lights"}, blocking=True
    )
    await hass.async_block_till_done()

    events = async_capture_events(hass, EVENT_COMMAND_RECEIVED)
    service_events = async_capture_events(hass, EVENT_CALL_SERVICE)

    platforms = entity_platform.async_get_platforms(hass, "demo")
    assert platforms[0].domain == "light"
    assert platforms[0].entities["light.ceiling_lights"]

    turn_on_wait = asyncio.Event()

    async def slow_turn_on(*args, **kwargs):
        # Make DemoLigt.async_turn_on hang waiting for the turn_on_wait event
        await turn_on_wait.wait(),

    with patch.object(
        hass.services, "async_call", wraps=hass.services.async_call
    ) as call_service_mock, patch.object(
        DemoLight, "async_turn_on", wraps=slow_turn_on
    ):
        result = await sh.async_handle_message(
            hass,
            MockConfig(should_report_state=report_state),
            None,
            {
                "requestId": REQ_ID,
                "inputs": [
                    {
                        "intent": "action.devices.EXECUTE",
                        "payload": {
                            "commands": [
                                {
                                    "devices": [
                                        {"id": "light.non_existing"},
                                        {"id": "light.ceiling_lights"},
                                        {"id": "light.kitchen_lights"},
                                    ],
                                    "execution": [
                                        {
                                            "command": "action.devices.commands.OnOff",
                                            "params": {"on": True},
                                        },
                                        {
                                            "command": "action.devices.commands.BrightnessAbsolute",
                                            "params": {"brightness": 20},
                                        },
                                    ],
                                }
                            ]
                        },
                    }
                ],
            },
            const.SOURCE_CLOUD,
        )
        # Only the two first calls are executed
        assert call_service_mock.call_count == 2
        expected_calls = [
            call(
                "light",
                "turn_on",
                {"entity_id": "light.ceiling_lights"},
                blocking=not report_state,
                context=ANY,
            ),
            call(
                "light",
                "turn_on",
                {"entity_id": "light.kitchen_lights"},
                blocking=not report_state,
                context=ANY,
            ),
        ]
        call_service_mock.assert_has_awaits(expected_calls, any_order=True)

        turn_on_wait.set()
        await hass.async_block_till_done()
        # The remaining two calls should now have executed
        assert call_service_mock.call_count == 4
        expected_calls.extend(
            [
                call(
                    "light",
                    "turn_on",
                    {"entity_id": "light.ceiling_lights", "brightness_pct": 20},
                    blocking=not report_state,
                    context=ANY,
                ),
                call(
                    "light",
                    "turn_on",
                    {"entity_id": "light.kitchen_lights", "brightness_pct": 20},
                    blocking=not report_state,
                    context=ANY,
                ),
            ]
        )
        call_service_mock.assert_has_awaits(expected_calls, any_order=True)
    await hass.async_block_till_done()

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "commands": [
                {
                    "ids": ["light.non_existing"],
                    "status": "ERROR",
                    "errorCode": "deviceOffline",
                },
                {
                    "ids": ["light.ceiling_lights"],
                    "status": "SUCCESS",
                    "states": {
                        "on": on,
                        "online": True,
                    },
                },
                {
                    "ids": ["light.kitchen_lights"],
                    "status": "SUCCESS",
                    "states": {
                        "on": True,
                        "online": True,
                        "brightness": brightness,
                        "color": {
                            "spectrumHsv": {
                                "hue": 345,
                                "saturation": 0.75,
                                "value": value,
                            },
                        },
                    },
                },
            ]
        },
    }

    assert len(events) == 1
    assert events[0].event_type == EVENT_COMMAND_RECEIVED
    assert events[0].data == {
        "request_id": REQ_ID,
        "entity_id": [
            "light.non_existing",
            "light.ceiling_lights",
            "light.kitchen_lights",
        ],
        "execution": [
            {
                "command": "action.devices.commands.OnOff",
                "params": {"on": True},
            },
            {
                "command": "action.devices.commands.BrightnessAbsolute",
                "params": {"brightness": 20},
            },
        ],
        "source": "cloud",
    }

    service_events = sorted(
        service_events, key=lambda ev: ev.data["service_data"]["entity_id"]
    )
    assert len(service_events) == 4
    assert service_events[0].data == {
        "domain": "light",
        "service": "turn_on",
        "service_data": {"entity_id": "light.ceiling_lights"},
    }
    assert service_events[1].data == {
        "domain": "light",
        "service": "turn_on",
        "service_data": {"brightness_pct": 20, "entity_id": "light.ceiling_lights"},
    }
    assert service_events[0].context == events[0].context
    assert service_events[1].context == events[0].context
    assert service_events[2].data == {
        "domain": "light",
        "service": "turn_on",
        "service_data": {"entity_id": "light.kitchen_lights"},
    }
    assert service_events[3].data == {
        "domain": "light",
        "service": "turn_on",
        "service_data": {"brightness_pct": 20, "entity_id": "light.kitchen_lights"},
    }
    assert service_events[2].context == events[0].context
    assert service_events[3].context == events[0].context

    sh.EXECUTE_LIMIT = orig_execute_limit


async def test_raising_error_trait(hass: HomeAssistant) -> None:
    """Test raising an error while executing a trait command."""
    hass.states.async_set(
        "climate.bla",
        HVACMode.HEAT,
        {
            ATTR_MIN_TEMP: 15,
            ATTR_MAX_TEMP: 30,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )

    events = async_capture_events(hass, EVENT_COMMAND_RECEIVED)
    await hass.async_block_till_done()

    result = await sh.async_handle_message(
        hass,
        BASIC_CONFIG,
        "test-agent",
        {
            "requestId": REQ_ID,
            "inputs": [
                {
                    "intent": "action.devices.EXECUTE",
                    "payload": {
                        "commands": [
                            {
                                "devices": [{"id": "climate.bla"}],
                                "execution": [
                                    {
                                        "command": "action.devices.commands."
                                        "ThermostatTemperatureSetpoint",
                                        "params": {"thermostatTemperatureSetpoint": 10},
                                    }
                                ],
                            }
                        ]
                    },
                }
            ],
        },
        const.SOURCE_CLOUD,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "commands": [
                {
                    "ids": ["climate.bla"],
                    "status": "ERROR",
                    "errorCode": "valueOutOfRange",
                }
            ]
        },
    }

    assert len(events) == 1
    assert events[0].event_type == EVENT_COMMAND_RECEIVED
    assert events[0].data == {
        "request_id": REQ_ID,
        "entity_id": ["climate.bla"],
        "execution": [
            {
                "command": "action.devices.commands.ThermostatTemperatureSetpoint",
                "params": {"thermostatTemperatureSetpoint": 10},
            }
        ],
        "source": "cloud",
    }


async def test_serialize_input_boolean(hass: HomeAssistant) -> None:
    """Test serializing an input boolean entity."""
    state = State("input_boolean.bla", "on")
    entity = sh.GoogleEntity(hass, BASIC_CONFIG, state)
    result = entity.sync_serialize(None, "mock-uuid")
    assert result == {
        "id": "input_boolean.bla",
        "attributes": {},
        "name": {"name": "bla"},
        "traits": ["action.devices.traits.OnOff"],
        "type": "action.devices.types.SWITCH",
        "willReportState": False,
    }


async def test_unavailable_state_does_sync(hass: HomeAssistant) -> None:
    """Test that an unavailable entity does sync over."""
    light = DemoLight(
        None,
        "Demo Light",
        state=False,
        hs_color=(180, 75),
        effect_list=LIGHT_EFFECT_LIST,
        effect=LIGHT_EFFECT_LIST[0],
    )
    light.hass = hass
    light.entity_id = "light.demo_light"
    light._available = False
    await light.async_update_ha_state()

    events = async_capture_events(hass, EVENT_SYNC_RECEIVED)

    result = await sh.async_handle_message(
        hass,
        BASIC_CONFIG,
        "test-agent",
        {"requestId": REQ_ID, "inputs": [{"intent": "action.devices.SYNC"}]},
        const.SOURCE_CLOUD,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "agentUserId": "test-agent",
            "devices": [
                {
                    "id": "light.demo_light",
                    "name": {"name": "Demo Light"},
                    "traits": [
                        trait.TRAIT_BRIGHTNESS,
                        trait.TRAIT_ONOFF,
                        trait.TRAIT_COLOR_SETTING,
                        trait.TRAIT_MODES,
                    ],
                    "type": const.TYPE_LIGHT,
                    "willReportState": False,
                    "attributes": {
                        "availableModes": [
                            {
                                "name": "effect",
                                "name_values": [
                                    {"lang": "en", "name_synonym": ["effect"]}
                                ],
                                "ordered": False,
                                "settings": [
                                    {
                                        "setting_name": "rainbow",
                                        "setting_values": [
                                            {
                                                "lang": "en",
                                                "setting_synonym": ["rainbow"],
                                            }
                                        ],
                                    },
                                    {
                                        "setting_name": "none",
                                        "setting_values": [
                                            {"lang": "en", "setting_synonym": ["none"]}
                                        ],
                                    },
                                ],
                            }
                        ],
                        "colorModel": "hsv",
                        "colorTemperatureRange": {
                            "temperatureMinK": 2000,
                            "temperatureMaxK": 6535,
                        },
                    },
                }
            ],
        },
    }
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == EVENT_SYNC_RECEIVED
    assert events[0].data == {"request_id": REQ_ID, "source": "cloud"}


@pytest.mark.parametrize(
    ("device_class", "google_type"),
    [
        ("non_existing_class", "action.devices.types.SWITCH"),
        ("switch", "action.devices.types.SWITCH"),
        ("outlet", "action.devices.types.OUTLET"),
    ],
)
async def test_device_class_switch(
    hass: HomeAssistant, device_class, google_type
) -> None:
    """Test that a cover entity syncs to the correct device type."""
    sensor = DemoSwitch(
        None,
        "Demo Sensor",
        state=False,
        icon="mdi:switch",
        assumed=False,
        device_class=device_class,
    )
    sensor.hass = hass
    sensor.entity_id = "switch.demo_sensor"
    await sensor.async_update_ha_state()

    result = await sh.async_handle_message(
        hass,
        BASIC_CONFIG,
        "test-agent",
        {"requestId": REQ_ID, "inputs": [{"intent": "action.devices.SYNC"}]},
        const.SOURCE_CLOUD,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "agentUserId": "test-agent",
            "devices": [
                {
                    "attributes": {},
                    "id": "switch.demo_sensor",
                    "name": {"name": "Demo Sensor"},
                    "traits": ["action.devices.traits.OnOff"],
                    "type": google_type,
                    "willReportState": False,
                }
            ],
        },
    }


@pytest.mark.parametrize(
    ("device_class", "google_type"),
    [
        ("door", "action.devices.types.DOOR"),
        ("garage_door", "action.devices.types.GARAGE"),
        ("lock", "action.devices.types.SENSOR"),
        ("opening", "action.devices.types.SENSOR"),
        ("window", "action.devices.types.WINDOW"),
    ],
)
async def test_device_class_binary_sensor(
    hass: HomeAssistant, device_class, google_type
) -> None:
    """Test that a binary entity syncs to the correct device type."""
    sensor = DemoBinarySensor(
        None, "Demo Sensor", state=False, device_class=device_class
    )
    sensor.hass = hass
    sensor.entity_id = "binary_sensor.demo_sensor"
    await sensor.async_update_ha_state()

    result = await sh.async_handle_message(
        hass,
        BASIC_CONFIG,
        "test-agent",
        {"requestId": REQ_ID, "inputs": [{"intent": "action.devices.SYNC"}]},
        const.SOURCE_CLOUD,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "agentUserId": "test-agent",
            "devices": [
                {
                    "attributes": {
                        "queryOnlyOpenClose": True,
                        "discreteOnlyOpenClose": True,
                    },
                    "id": "binary_sensor.demo_sensor",
                    "name": {"name": "Demo Sensor"},
                    "traits": ["action.devices.traits.OpenClose"],
                    "type": google_type,
                    "willReportState": False,
                }
            ],
        },
    }


@pytest.mark.parametrize(
    ("device_class", "google_type"),
    [
        ("non_existing_class", "action.devices.types.BLINDS"),
        ("door", "action.devices.types.DOOR"),
        ("garage", "action.devices.types.GARAGE"),
        ("gate", "action.devices.types.GARAGE"),
        ("awning", "action.devices.types.AWNING"),
        ("shutter", "action.devices.types.SHUTTER"),
        ("curtain", "action.devices.types.CURTAIN"),
    ],
)
async def test_device_class_cover(
    hass: HomeAssistant, device_class, google_type
) -> None:
    """Test that a cover entity syncs to the correct device type."""
    sensor = DemoCover(None, hass, "Demo Sensor", device_class=device_class)
    sensor.hass = hass
    sensor.entity_id = "cover.demo_sensor"
    await sensor.async_update_ha_state()

    result = await sh.async_handle_message(
        hass,
        BASIC_CONFIG,
        "test-agent",
        {"requestId": REQ_ID, "inputs": [{"intent": "action.devices.SYNC"}]},
        const.SOURCE_CLOUD,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "agentUserId": "test-agent",
            "devices": [
                {
                    "attributes": {"discreteOnlyOpenClose": True},
                    "id": "cover.demo_sensor",
                    "name": {"name": "Demo Sensor"},
                    "traits": [
                        "action.devices.traits.StartStop",
                        "action.devices.traits.OpenClose",
                    ],
                    "type": google_type,
                    "willReportState": False,
                }
            ],
        },
    }


@pytest.mark.parametrize(
    ("device_class", "google_type"),
    [
        ("non_existing_class", "action.devices.types.SETTOP"),
        ("tv", "action.devices.types.TV"),
        ("speaker", "action.devices.types.SPEAKER"),
        ("receiver", "action.devices.types.AUDIO_VIDEO_RECEIVER"),
    ],
)
async def test_device_media_player(
    hass: HomeAssistant, device_class, google_type
) -> None:
    """Test that a binary entity syncs to the correct device type."""
    sensor = AbstractDemoPlayer("Demo", device_class=device_class)
    sensor.hass = hass
    sensor.entity_id = "media_player.demo"
    await sensor.async_update_ha_state()

    result = await sh.async_handle_message(
        hass,
        BASIC_CONFIG,
        "test-agent",
        {"requestId": REQ_ID, "inputs": [{"intent": "action.devices.SYNC"}]},
        const.SOURCE_CLOUD,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "agentUserId": "test-agent",
            "devices": [
                {
                    "attributes": {
                        "supportActivityState": True,
                        "supportPlaybackState": True,
                    },
                    "id": sensor.entity_id,
                    "name": {"name": sensor.name},
                    "traits": [
                        "action.devices.traits.OnOff",
                        "action.devices.traits.MediaState",
                    ],
                    "type": google_type,
                    "willReportState": False,
                }
            ],
        },
    }


async def test_query_disconnect(hass: HomeAssistant) -> None:
    """Test a disconnect message."""
    config = MockConfig(hass=hass)
    config.async_enable_report_state()
    assert config._unsub_report_state is not None
    with patch.object(config, "async_disconnect_agent_user") as mock_disconnect:
        result = await sh.async_handle_message(
            hass,
            config,
            "test-agent",
            {"inputs": [{"intent": "action.devices.DISCONNECT"}], "requestId": REQ_ID},
            const.SOURCE_CLOUD,
        )
    assert result is None
    assert len(mock_disconnect.mock_calls) == 1


async def test_trait_execute_adding_query_data(hass: HomeAssistant) -> None:
    """Test a trait execute influencing query data."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    hass.states.async_set(
        "camera.office", "idle", {"supported_features": camera.SUPPORT_STREAM}
    )

    with patch(
        "homeassistant.components.camera.async_request_stream",
        return_value="/api/streams/bla",
    ):
        result = await sh.async_handle_message(
            hass,
            BASIC_CONFIG,
            None,
            {
                "requestId": REQ_ID,
                "inputs": [
                    {
                        "intent": "action.devices.EXECUTE",
                        "payload": {
                            "commands": [
                                {
                                    "devices": [{"id": "camera.office"}],
                                    "execution": [
                                        {
                                            "command": "action.devices.commands.GetCameraStream",
                                            "params": {
                                                "StreamToChromecast": True,
                                                "SupportedStreamProtocols": [
                                                    "progressive_mp4",
                                                    "hls",
                                                    "dash",
                                                    "smooth_stream",
                                                ],
                                            },
                                        }
                                    ],
                                }
                            ]
                        },
                    }
                ],
            },
            const.SOURCE_CLOUD,
        )

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "commands": [
                {
                    "ids": ["camera.office"],
                    "status": "SUCCESS",
                    "states": {
                        "online": True,
                        "cameraStreamAccessUrl": "https://example.com/api/streams/bla",
                        "cameraStreamReceiverAppId": "B45F4572",
                    },
                }
            ]
        },
    }


async def test_identify(hass: HomeAssistant) -> None:
    """Test identify message."""
    user_agent_id = "mock-user-id"
    proxy_device_id = user_agent_id
    result = await sh.async_handle_message(
        hass,
        BASIC_CONFIG,
        user_agent_id,
        {
            "requestId": REQ_ID,
            "inputs": [
                {
                    "intent": "action.devices.IDENTIFY",
                    "payload": {
                        "device": {
                            "mdnsScanData": {
                                "additionals": [
                                    {
                                        "type": "TXT",
                                        "class": "IN",
                                        "name": "devhome._home-assistant._tcp.local",
                                        "ttl": 4500,
                                        "data": [
                                            "version=0.101.0.dev0",
                                            "base_url=http://192.168.1.101:8123",
                                            "requires_api_password=true",
                                        ],
                                    }
                                ]
                            }
                        },
                        "structureData": {},
                    },
                }
            ],
            "devices": [
                {
                    "id": "light.ceiling_lights",
                    "customData": {
                        "httpPort": 8123,
                        "httpSSL": False,
                        "proxyDeviceId": proxy_device_id,
                        "webhookId": "dde3b9800a905e886cc4d38e226a6e7e3f2a6993d2b9b9f63d13e42ee7de3219",
                    },
                }
            ],
        },
        const.SOURCE_CLOUD,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "device": {
                "id": proxy_device_id,
                "isLocalOnly": True,
                "isProxy": True,
                "deviceInfo": {
                    "hwVersion": "UNKNOWN_HW_VERSION",
                    "manufacturer": "Home Assistant",
                    "model": "Home Assistant",
                    "swVersion": __version__,
                },
            }
        },
    }


async def test_reachable_devices(hass: HomeAssistant) -> None:
    """Test REACHABLE_DEVICES intent."""
    # Matching passed in device.
    hass.states.async_set("light.ceiling_lights", "on")

    # Unsupported entity
    hass.states.async_set("not_supported.entity", "something")

    # Excluded via config
    hass.states.async_set("light.not_expose", "on")

    # Not passed in as google_id
    hass.states.async_set("light.not_mentioned", "on")

    # Has 2FA
    hass.states.async_set("lock.has_2fa", "on")

    config = MockConfig(
        should_expose=lambda state: state.entity_id != "light.not_expose",
    )

    user_agent_id = "mock-user-id"
    proxy_device_id = user_agent_id

    result = await sh.async_handle_message(
        hass,
        config,
        user_agent_id,
        {
            "requestId": REQ_ID,
            "inputs": [
                {
                    "intent": "action.devices.REACHABLE_DEVICES",
                    "payload": {
                        "device": {
                            "proxyDevice": {
                                "id": proxy_device_id,
                                "customData": "{}",
                                "proxyData": "{}",
                            }
                        },
                        "structureData": {},
                    },
                }
            ],
            "devices": [
                {
                    "id": "light.ceiling_lights",
                    "customData": {
                        "httpPort": 8123,
                        "httpSSL": False,
                        "proxyDeviceId": proxy_device_id,
                        "webhookId": "dde3b9800a905e886cc4d38e226a6e7e3f2a6993d2b9b9f63d13e42ee7de3219",
                    },
                },
                {
                    "id": "light.not_expose",
                    "customData": {
                        "httpPort": 8123,
                        "httpSSL": False,
                        "proxyDeviceId": proxy_device_id,
                        "webhookId": "dde3b9800a905e886cc4d38e226a6e7e3f2a6993d2b9b9f63d13e42ee7de3219",
                    },
                },
                {
                    "id": "lock.has_2fa",
                    "customData": {
                        "httpPort": 8123,
                        "httpSSL": False,
                        "proxyDeviceId": proxy_device_id,
                        "webhookId": "dde3b9800a905e886cc4d38e226a6e7e3f2a6993d2b9b9f63d13e42ee7de3219",
                    },
                },
                {"id": proxy_device_id, "customData": {}},
            ],
        },
        const.SOURCE_CLOUD,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {"devices": [{"verificationId": "light.ceiling_lights"}]},
    }


async def test_sync_message_recovery(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a sync message recovers from bad entities."""
    light = DemoLight(
        None,
        "Demo Light",
        state=False,
        hs_color=(180, 75),
    )
    light.hass = hass
    light.entity_id = "light.demo_light"
    await light.async_update_ha_state()

    hass.states.async_set(
        "light.bad_light",
        "on",
        {
            "min_mireds": "badvalue",
            "supported_color_modes": ["color_temp"],
        },
    )

    result = await sh.async_handle_message(
        hass,
        BASIC_CONFIG,
        "test-agent",
        {"requestId": REQ_ID, "inputs": [{"intent": "action.devices.SYNC"}]},
        const.SOURCE_CLOUD,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "agentUserId": "test-agent",
            "devices": [
                {
                    "id": "light.demo_light",
                    "name": {"name": "Demo Light"},
                    "attributes": {
                        "colorModel": "hsv",
                        "colorTemperatureRange": {
                            "temperatureMaxK": 6535,
                            "temperatureMinK": 2000,
                        },
                    },
                    "traits": [
                        "action.devices.traits.Brightness",
                        "action.devices.traits.OnOff",
                        "action.devices.traits.ColorSetting",
                    ],
                    "willReportState": False,
                    "type": "action.devices.types.LIGHT",
                },
            ],
        },
    }

    assert "Error serializing light.bad_light" in caplog.text


async def test_query_recover(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that we recover if an entity raises during query."""

    hass.states.async_set(
        "light.good",
        "on",
        {
            "supported_color_modes": ["brightness"],
            "brightness": 50,
        },
    )
    hass.states.async_set(
        "light.bad",
        "on",
        {
            "supported_color_modes": ["brightness"],
            "brightness": "shoe",
        },
    )

    result = await sh.async_handle_message(
        hass,
        BASIC_CONFIG,
        "test-agent",
        {
            "requestId": REQ_ID,
            "inputs": [
                {
                    "intent": "action.devices.QUERY",
                    "payload": {
                        "devices": [
                            {"id": "light.good"},
                            {"id": "light.bad"},
                        ]
                    },
                }
            ],
        },
        const.SOURCE_CLOUD,
    )

    assert (
        f"Unexpected error serializing query for {hass.states.get('light.bad')}"
        in caplog.text
    )
    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "devices": {
                "light.bad": {"online": False},
                "light.good": {"on": True, "online": True, "brightness": 20},
            }
        },
    }


async def test_proxy_selected(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that we handle proxy selected."""

    result = await sh.async_handle_message(
        hass,
        BASIC_CONFIG,
        "test-agent",
        {
            "requestId": REQ_ID,
            "inputs": [
                {
                    "intent": "action.devices.PROXY_SELECTED",
                    "payload": {
                        "device": {
                            "id": "abcdefg",
                            "customData": {},
                        },
                        "structureData": {},
                    },
                }
            ],
        },
        const.SOURCE_LOCAL,
    )

    assert result == {
        "requestId": REQ_ID,
        "payload": {},
    }
