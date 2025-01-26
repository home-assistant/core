"""The tests for the Google Assistant component."""

from asyncio import AbstractEventLoop
from http import HTTPStatus
import json
from unittest.mock import patch

from aiohttp.hdrs import AUTHORIZATION
from aiohttp.test_utils import TestClient
import pytest

from homeassistant import const, core, setup
from homeassistant.components import (
    google_assistant as ga,
    humidifier,
    light,
    media_player,
)
from homeassistant.const import (
    CLOUD_NEVER_EXPOSED_ENTITIES,
    EntityCategory,
    Platform,
    UnitOfTemperature,
)
from homeassistant.helpers import entity_registry as er

from . import DEMO_DEVICES

from tests.typing import ClientSessionGenerator

API_PASSWORD = "test1234"

PROJECT_ID = "hasstest-1234"
CLIENT_ID = "helloworld"
ACCESS_TOKEN = "superdoublesecret"


@pytest.fixture
def auth_header(hass_access_token: str) -> dict[str, str]:
    """Generate an HTTP header with bearer token authorization."""
    return {AUTHORIZATION: f"Bearer {hass_access_token}"}


@pytest.fixture
def assistant_client(
    event_loop: AbstractEventLoop,
    hass: core.HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> TestClient:
    """Create web client for the Google Assistant API."""
    loop = event_loop
    loop.run_until_complete(
        setup.async_setup_component(
            hass,
            "google_assistant",
            {
                "google_assistant": {
                    "project_id": PROJECT_ID,
                    "entity_config": {
                        "light.ceiling_lights": {
                            "aliases": ["top lights", "ceiling lights"],
                            "name": "Roof Lights",
                        }
                    },
                }
            },
        )
    )

    return loop.run_until_complete(hass_client_no_auth())


@pytest.fixture(autouse=True)
async def wanted_platforms_only() -> None:
    """Enable only the wanted demo platforms."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [
            Platform.ALARM_CONTROL_PANEL,
            Platform.CLIMATE,
            Platform.COVER,
            Platform.FAN,
            Platform.HUMIDIFIER,
            Platform.LIGHT,
            Platform.LOCK,
            Platform.MEDIA_PLAYER,
            Platform.SWITCH,
        ],
    ):
        yield


@pytest.fixture
def hass_fixture(
    event_loop: AbstractEventLoop, hass: core.HomeAssistant
) -> core.HomeAssistant:
    """Set up a Home Assistant instance for these tests."""
    loop = event_loop

    # We need to do this to get access to homeassistant/turn_(on,off)
    loop.run_until_complete(setup.async_setup_component(hass, core.DOMAIN, {}))

    loop.run_until_complete(setup.async_setup_component(hass, "demo", {}))

    return hass


async def test_sync_request(
    hass_fixture, assistant_client, auth_header, entity_registry: er.EntityRegistry
) -> None:
    """Test a sync request."""
    entity_entry1 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "switch_config_id",
        suggested_object_id="config_switch",
        entity_category=EntityCategory.CONFIG,
    )
    entity_entry2 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "switch_diagnostic_id",
        suggested_object_id="diagnostic_switch",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    entity_entry3 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "switch_hidden_integration_id",
        suggested_object_id="hidden_integration_switch",
        hidden_by=er.RegistryEntryHider.INTEGRATION,
    )
    entity_entry4 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "switch_hidden_user_id",
        suggested_object_id="hidden_user_switch",
        hidden_by=er.RegistryEntryHider.USER,
    )

    # These should not show up in the sync request
    hass_fixture.states.async_set(entity_entry1.entity_id, "on")
    hass_fixture.states.async_set(entity_entry2.entity_id, "something_else")
    hass_fixture.states.async_set(entity_entry3.entity_id, "blah")
    hass_fixture.states.async_set(entity_entry4.entity_id, "foo")

    reqid = "5711642932632160983"
    data = {"requestId": reqid, "inputs": [{"intent": "action.devices.SYNC"}]}
    result = await assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=auth_header,
    )
    assert result.status == HTTPStatus.OK
    body = await result.json()
    assert body.get("requestId") == reqid
    devices = body["payload"]["devices"]
    assert sorted(dev["id"] for dev in devices) == sorted(
        dev["id"] for dev in DEMO_DEVICES
    )

    for dev in devices:
        assert dev["id"] not in CLOUD_NEVER_EXPOSED_ENTITIES

    for dev, demo in zip(
        sorted(devices, key=lambda d: d["id"]),
        sorted(DEMO_DEVICES, key=lambda d: d["id"]),
        strict=False,
    ):
        assert dev["name"] == demo["name"]
        assert set(dev["traits"]) == set(demo["traits"])
        assert dev["type"] == demo["type"]


async def test_query_request(hass_fixture, assistant_client, auth_header) -> None:
    """Test a query request."""
    reqid = "5711642932632160984"
    data = {
        "requestId": reqid,
        "inputs": [
            {
                "intent": "action.devices.QUERY",
                "payload": {
                    "devices": [
                        {"id": "light.ceiling_lights"},
                        {"id": "light.bed_light"},
                        {"id": "light.kitchen_lights"},
                        {"id": "media_player.lounge_room"},
                    ]
                },
            }
        ],
    }
    result = await assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=auth_header,
    )
    assert result.status == HTTPStatus.OK
    body = await result.json()
    assert body.get("requestId") == reqid
    devices = body["payload"]["devices"]
    assert len(devices) == 4
    assert devices["light.bed_light"]["on"] is False
    assert devices["light.ceiling_lights"]["on"] is True
    assert devices["light.ceiling_lights"]["brightness"] == 71
    assert devices["light.ceiling_lights"]["color"]["temperatureK"] == 2631
    assert devices["light.kitchen_lights"]["color"]["spectrumHsv"] == {
        "hue": 345,
        "saturation": 0.75,
        "value": 0.7058823529411765,
    }
    assert devices["media_player.lounge_room"]["on"] is True


async def test_query_climate_request(
    hass_fixture, assistant_client, auth_header
) -> None:
    """Test a query request."""
    reqid = "5711642932632160984"
    data = {
        "requestId": reqid,
        "inputs": [
            {
                "intent": "action.devices.QUERY",
                "payload": {
                    "devices": [
                        {"id": "climate.hvac"},
                        {"id": "climate.heatpump"},
                        {"id": "climate.ecobee"},
                    ]
                },
            }
        ],
    }
    result = await assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=auth_header,
    )
    assert result.status == HTTPStatus.OK
    body = await result.json()
    assert body.get("requestId") == reqid
    devices = body["payload"]["devices"]
    assert len(devices) == 3
    assert devices["climate.heatpump"] == {
        "online": True,
        "on": True,
        "thermostatTemperatureSetpoint": 20.0,
        "thermostatTemperatureAmbient": 25.0,
        "thermostatMode": "heat",
    }
    assert devices["climate.ecobee"] == {
        "online": True,
        "on": True,
        "thermostatTemperatureSetpointHigh": 24,
        "thermostatTemperatureAmbient": 23,
        "thermostatMode": "heatcool",
        "thermostatTemperatureSetpointLow": 21,
        "currentFanSpeedSetting": "auto_low",
    }
    assert devices["climate.hvac"] == {
        "online": True,
        "on": True,
        "thermostatTemperatureSetpoint": 21,
        "thermostatTemperatureAmbient": 22,
        "thermostatMode": "cool",
        "thermostatHumidityAmbient": 54.2,
        "currentFanSpeedSetting": "on_high",
    }


async def test_query_climate_request_f(
    hass_fixture, assistant_client, auth_header
) -> None:
    """Test a query request."""
    # Mock demo devices as fahrenheit to see if we convert to celsius
    hass_fixture.config.units.temperature_unit = UnitOfTemperature.FAHRENHEIT
    for entity_id in ("climate.hvac", "climate.heatpump", "climate.ecobee"):
        state = hass_fixture.states.get(entity_id)
        attr = dict(state.attributes)
        hass_fixture.states.async_set(entity_id, state.state, attr)

    reqid = "5711642932632160984"
    data = {
        "requestId": reqid,
        "inputs": [
            {
                "intent": "action.devices.QUERY",
                "payload": {
                    "devices": [
                        {"id": "climate.hvac"},
                        {"id": "climate.heatpump"},
                        {"id": "climate.ecobee"},
                    ]
                },
            }
        ],
    }
    result = await assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=auth_header,
    )
    assert result.status == HTTPStatus.OK
    body = await result.json()
    assert body.get("requestId") == reqid
    devices = body["payload"]["devices"]
    assert len(devices) == 3
    assert devices["climate.heatpump"] == {
        "online": True,
        "on": True,
        "thermostatTemperatureSetpoint": -6.7,
        "thermostatTemperatureAmbient": -3.9,
        "thermostatMode": "heat",
    }
    assert devices["climate.ecobee"] == {
        "online": True,
        "on": True,
        "thermostatTemperatureSetpointHigh": -4.4,
        "thermostatTemperatureAmbient": -5,
        "thermostatMode": "heatcool",
        "thermostatTemperatureSetpointLow": -6.1,
        "currentFanSpeedSetting": "auto_low",
    }
    assert devices["climate.hvac"] == {
        "online": True,
        "on": True,
        "thermostatTemperatureSetpoint": -6.1,
        "thermostatTemperatureAmbient": -5.6,
        "thermostatMode": "cool",
        "thermostatHumidityAmbient": 54.2,
        "currentFanSpeedSetting": "on_high",
    }
    hass_fixture.config.units.temperature_unit = UnitOfTemperature.CELSIUS


async def test_query_humidifier_request(
    hass_fixture, assistant_client, auth_header
) -> None:
    """Test a query request."""
    reqid = "5711642932632160984"
    data = {
        "requestId": reqid,
        "inputs": [
            {
                "intent": "action.devices.QUERY",
                "payload": {
                    "devices": [
                        {"id": "humidifier.humidifier"},
                        {"id": "humidifier.dehumidifier"},
                        {"id": "humidifier.hygrostat"},
                    ]
                },
            }
        ],
    }
    result = await assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=auth_header,
    )
    assert result.status == HTTPStatus.OK
    body = await result.json()
    assert body.get("requestId") == reqid
    devices = body["payload"]["devices"]
    assert len(devices) == 3
    assert devices["humidifier.humidifier"] == {
        "on": True,
        "online": True,
        "humiditySetpointPercent": 68,
        "humidityAmbientPercent": 45,
    }
    assert devices["humidifier.dehumidifier"] == {
        "on": True,
        "online": True,
        "humiditySetpointPercent": 54.2,
        "humidityAmbientPercent": 59.4,
    }
    assert devices["humidifier.hygrostat"] == {
        "on": True,
        "online": True,
        "humiditySetpointPercent": 50,
        "currentModeSettings": {"mode": "home"},
    }


async def test_execute_request(hass_fixture, assistant_client, auth_header) -> None:
    """Test an execute request."""
    reqid = "5711642932632160985"
    data = {
        "requestId": reqid,
        "inputs": [
            {
                "intent": "action.devices.EXECUTE",
                "payload": {
                    "commands": [
                        {
                            "devices": [
                                {"id": "light.ceiling_lights"},
                                {"id": "switch.decorative_lights"},
                                {"id": "media_player.lounge_room"},
                            ],
                            "execution": [
                                {
                                    "command": "action.devices.commands.OnOff",
                                    "params": {"on": False},
                                }
                            ],
                        },
                        {
                            "devices": [{"id": "media_player.walkman"}],
                            "execution": [
                                {
                                    "command": "action.devices.commands.setVolume",
                                    "params": {"volumeLevel": 70},
                                }
                            ],
                        },
                        {
                            "devices": [{"id": "light.kitchen_lights"}],
                            "execution": [
                                {
                                    "command": "action.devices.commands.ColorAbsolute",
                                    "params": {"color": {"spectrumRGB": 16711680}},
                                }
                            ],
                        },
                        {
                            "devices": [{"id": "light.bed_light"}],
                            "execution": [
                                {
                                    "command": "action.devices.commands.ColorAbsolute",
                                    "params": {"color": {"spectrumRGB": 65280}},
                                },
                                {
                                    "command": "action.devices.commands.ColorAbsolute",
                                    "params": {"color": {"temperature": 4700}},
                                },
                            ],
                        },
                        {
                            "devices": [{"id": "humidifier.humidifier"}],
                            "execution": [
                                {
                                    "command": "action.devices.commands.OnOff",
                                    "params": {"on": False},
                                }
                            ],
                        },
                        {
                            "devices": [{"id": "humidifier.dehumidifier"}],
                            "execution": [
                                {
                                    "command": "action.devices.commands.SetHumidity",
                                    "params": {"humidity": 45},
                                }
                            ],
                        },
                        {
                            "devices": [{"id": "humidifier.hygrostat"}],
                            "execution": [
                                {
                                    "command": "action.devices.commands.SetModes",
                                    "params": {"updateModeSettings": {"mode": "eco"}},
                                }
                            ],
                        },
                    ]
                },
            }
        ],
    }
    result = await assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=auth_header,
    )
    assert result.status == HTTPStatus.OK
    body = await result.json()
    assert body.get("requestId") == reqid
    commands = body["payload"]["commands"]
    assert len(commands) == 9

    assert not any(result["status"] == "ERROR" for result in commands)

    ceiling = hass_fixture.states.get("light.ceiling_lights")
    assert ceiling.state == "off"

    kitchen = hass_fixture.states.get("light.kitchen_lights")
    assert kitchen.attributes.get(light.ATTR_RGB_COLOR) == (255, 0, 0)

    bed = hass_fixture.states.get("light.bed_light")
    assert bed.attributes.get(light.ATTR_COLOR_TEMP_KELVIN) == 4700

    assert hass_fixture.states.get("switch.decorative_lights").state == "off"

    walkman = hass_fixture.states.get("media_player.walkman")
    assert walkman.state == "playing"
    assert walkman.attributes.get(media_player.ATTR_MEDIA_VOLUME_LEVEL) == 0.7

    lounge = hass_fixture.states.get("media_player.lounge_room")
    assert lounge.state == "off"

    humidifier_state = hass_fixture.states.get("humidifier.humidifier")
    assert humidifier_state.state == "off"

    dehumidifier = hass_fixture.states.get("humidifier.dehumidifier")
    assert dehumidifier.attributes.get(humidifier.ATTR_HUMIDITY) == 45

    hygrostat = hass_fixture.states.get("humidifier.hygrostat")
    assert hygrostat.attributes.get(const.ATTR_MODE) == "eco"
