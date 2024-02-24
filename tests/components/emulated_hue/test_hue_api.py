"""The tests for the emulated Hue component."""
import asyncio
from datetime import timedelta
from http import HTTPStatus
from ipaddress import ip_address
import json
from unittest.mock import patch

from aiohttp.hdrs import CONTENT_TYPE
import pytest

from homeassistant import const, setup
from homeassistant.components import (
    climate,
    cover,
    emulated_hue,
    fan,
    http,
    humidifier,
    light,
    media_player,
    script,
)
from homeassistant.components.emulated_hue import Config, hue_api
from homeassistant.components.emulated_hue.hue_api import (
    HUE_API_STATE_BRI,
    HUE_API_STATE_BRI_MAX,
    HUE_API_STATE_CT,
    HUE_API_STATE_HUE,
    HUE_API_STATE_ON,
    HUE_API_STATE_SAT,
    HUE_API_STATE_TRANSITION,
    HUE_API_STATE_XY,
    HUE_API_USERNAME,
    HueAllGroupsStateView,
    HueAllLightsStateView,
    HueConfigView,
    HueFullStateView,
    HueGroupView,
    HueOneLightChangeView,
    HueOneLightStateView,
    HueUsernameView,
    _remote_is_allowed,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONTENT_TYPE_JSON,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from tests.common import (
    async_fire_time_changed,
    async_mock_service,
    get_test_instance_port,
)
from tests.typing import ClientSessionGenerator

HTTP_SERVER_PORT = get_test_instance_port()
BRIDGE_SERVER_PORT = get_test_instance_port()

BRIDGE_URL_BASE = f"http://127.0.0.1:{BRIDGE_SERVER_PORT}" + "{}"
JSON_HEADERS = {CONTENT_TYPE: const.CONTENT_TYPE_JSON}

ENTITY_IDS_BY_NUMBER = {
    "1": "light.ceiling_lights",
    "2": "light.bed_light",
    "3": "script.set_kitchen_light",
    "4": "light.kitchen_lights",
    "5": "media_player.living_room",
    "6": "media_player.bedroom",
    "7": "media_player.walkman",
    "8": "media_player.lounge_room",
    "9": "fan.living_room_fan",
    "10": "fan.ceiling_fan",
    "11": "fan.percentage_full_fan",
    "12": "fan.percentage_limited_fan",
    "13": "fan.preset_only_limited_fan",
    "14": "cover.living_room_window",
    "15": "climate.hvac",
    "16": "climate.heatpump",
    "17": "climate.ecobee",
    "18": "light.no_brightness",
    "19": "humidifier.humidifier",
    "20": "humidifier.dehumidifier",
    "21": "humidifier.hygrostat",
    "22": "scene.light_on",
    "23": "scene.light_off",
    "24": "media_player.kitchen",
    "25": "light.office_rgbw_lights",
    "26": "light.living_room_rgbww_lights",
    "27": "media_player.group",
    "28": "media_player.browse",
}

ENTITY_NUMBERS_BY_ID = {v: k for k, v in ENTITY_IDS_BY_NUMBER.items()}


def patch_upnp():
    """Patch async_create_upnp_datagram_endpoint."""
    return patch(
        "homeassistant.components.emulated_hue.async_create_upnp_datagram_endpoint"
    )


async def async_get_lights(client):
    """Get lights with the hue client."""
    result = await client.get("/api/username/lights")
    assert result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in result.headers["content-type"]
    return await result.json()


async def _async_setup_emulated_hue(hass: HomeAssistant, conf: ConfigType) -> None:
    """Set up emulated_hue with a specific config."""
    with patch_upnp():
        await setup.async_setup_component(
            hass,
            emulated_hue.DOMAIN,
            {emulated_hue.DOMAIN: conf},
        )
        await hass.async_block_till_done()


@pytest.fixture
async def base_setup(hass):
    """Set up homeassistant and http."""
    await asyncio.gather(
        setup.async_setup_component(hass, "homeassistant", {}),
        setup.async_setup_component(
            hass, http.DOMAIN, {http.DOMAIN: {http.CONF_SERVER_PORT: HTTP_SERVER_PORT}}
        ),
    )


@pytest.fixture(autouse=True)
async def wanted_platforms_only() -> None:
    """Enable only the wanted demo platforms."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [
            const.Platform.CLIMATE,
            const.Platform.COVER,
            const.Platform.FAN,
            const.Platform.HUMIDIFIER,
            const.Platform.LIGHT,
            const.Platform.MEDIA_PLAYER,
        ],
    ):
        yield


@pytest.fixture
async def demo_setup(hass, wanted_platforms_only):
    """Fixture to setup demo platforms."""
    # We need to do this to get access to homeassistant/turn_(on,off)
    setups = [
        setup.async_setup_component(hass, "homeassistant", {}),
        setup.async_setup_component(
            hass, http.DOMAIN, {http.DOMAIN: {http.CONF_SERVER_PORT: HTTP_SERVER_PORT}}
        ),
        setup.async_setup_component(hass, "demo", {}),
        setup.async_setup_component(
            hass,
            script.DOMAIN,
            {
                "script": {
                    "set_kitchen_light": {
                        "sequence": [
                            {
                                "service_template": "light.turn_{{ requested_state }}",
                                "data_template": {
                                    "entity_id": "light.kitchen_lights",
                                    "brightness": "{{ requested_level }}",
                                },
                            }
                        ]
                    }
                }
            },
        ),
        setup.async_setup_component(
            hass,
            "scene",
            {
                "scene": [
                    {
                        "id": "light_on",
                        "name": "Light on",
                        "entities": {"light.kitchen_lights": {"state": "on"}},
                    },
                    {
                        "id": "light_off",
                        "name": "Light off",
                        "entities": {"light.kitchen_lights": {"state": "off"}},
                    },
                ]
            },
        ),
    ]

    await asyncio.gather(*setups)


@pytest.fixture
async def hass_hue(hass, base_setup, demo_setup):
    """Set up a Home Assistant instance for these tests."""
    await _async_setup_emulated_hue(
        hass,
        {
            emulated_hue.CONF_LISTEN_PORT: BRIDGE_SERVER_PORT,
            emulated_hue.CONF_EXPOSE_BY_DEFAULT: True,
        },
    )
    # create a lamp without brightness support
    hass.states.async_set("light.no_brightness", "on", {})
    return hass


@callback
def _mock_hue_endpoints(
    hass: HomeAssistant, conf: ConfigType, entity_numbers: dict[str, str]
) -> None:
    """Override the hue config with specific entity numbers."""
    web_app = hass.http.app
    config = Config(hass, conf, "127.0.0.1")
    config.numbers = entity_numbers
    HueUsernameView().register(hass, web_app, web_app.router)
    HueAllLightsStateView(config).register(hass, web_app, web_app.router)
    HueOneLightStateView(config).register(hass, web_app, web_app.router)
    HueOneLightChangeView(config).register(hass, web_app, web_app.router)
    HueAllGroupsStateView(config).register(hass, web_app, web_app.router)
    HueGroupView(config).register(hass, web_app, web_app.router)
    HueFullStateView(config).register(hass, web_app, web_app.router)
    HueConfigView(config).register(hass, web_app, web_app.router)


@pytest.fixture
async def hue_client(hass_hue, hass_client_no_auth):
    """Create web client for emulated hue api."""
    _mock_hue_endpoints(
        hass_hue,
        {
            emulated_hue.CONF_ENTITIES: {
                "light.bed_light": {emulated_hue.CONF_ENTITY_HIDDEN: True},
                # Kitchen light is explicitly excluded from being exposed
                "light.kitchen_lights": {emulated_hue.CONF_ENTITY_HIDDEN: True},
                # Entrance light is explicitly excluded from being exposed
                "light.entrance_color_white_lights": {
                    emulated_hue.CONF_ENTITY_HIDDEN: True
                },
                # Ceiling Fan is explicitly excluded from being exposed
                "fan.ceiling_fan": {emulated_hue.CONF_ENTITY_HIDDEN: True},
                # Expose the script
                "script.set_kitchen_light": {emulated_hue.CONF_ENTITY_HIDDEN: False},
                # Expose cover
                "cover.living_room_window": {emulated_hue.CONF_ENTITY_HIDDEN: False},
                # Expose Hvac
                "climate.hvac": {emulated_hue.CONF_ENTITY_HIDDEN: False},
                # Expose HeatPump
                "climate.heatpump": {emulated_hue.CONF_ENTITY_HIDDEN: False},
                # Expose Humidifier
                "humidifier.humidifier": {emulated_hue.CONF_ENTITY_HIDDEN: False},
                # Expose Dehumidifier
                "humidifier.dehumidifier": {emulated_hue.CONF_ENTITY_HIDDEN: False},
                # No expose setting (use default of not exposed)
                "climate.nosetting": {},
                # Expose scenes
                "scene.light_on": {emulated_hue.CONF_ENTITY_HIDDEN: False},
                "scene.light_off": {emulated_hue.CONF_ENTITY_HIDDEN: False},
            },
        },
        ENTITY_IDS_BY_NUMBER,
    )
    return await hass_client_no_auth()


async def test_discover_lights(hass: HomeAssistant, hue_client) -> None:
    """Test the discovery of lights."""
    result = await hue_client.get("/api/username/lights")

    assert result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in result.headers["content-type"]

    result_json = await result.json()

    devices = {val["uniqueid"] for val in result_json.values()}

    # Make sure the lights we added to the config are there
    assert "00:2f:d2:31:ce:c5:55:cc-ee" in devices  # light.ceiling_lights
    assert "00:b6:14:77:34:b7:bb:06-e8" not in devices  # light.bed_light
    assert "00:95:b7:51:16:58:6c:c0-c5" in devices  # script.set_kitchen_light
    assert "00:64:7b:e4:96:c3:fe:90-c3" not in devices  # light.kitchen_lights
    assert "00:7e:8a:42:35:66:db:86-c5" in devices  # media_player.living_room
    assert "00:05:44:c2:d6:0a:e5:17-b7" in devices  # media_player.bedroom
    assert "00:f3:5f:fa:31:f3:32:21-a8" in devices  # media_player.walkman
    assert "00:b4:06:2e:91:95:23:97-fb" in devices  # media_player.lounge_room
    assert "00:b2:bd:f9:2c:ad:22:ae-58" in devices  # fan.living_room_fan
    assert "00:77:4c:8a:23:7d:27:4b-7f" not in devices  # fan.ceiling_fan
    assert "00:02:53:b9:d5:1a:b3:67-b2" in devices  # cover.living_room_window
    assert "00:42:03:fe:97:58:2d:b1-50" in devices  # climate.hvac
    assert "00:7b:2a:c7:08:d6:66:bf-80" in devices  # climate.heatpump
    assert "00:57:77:a1:6a:8e:ef:b3-6c" not in devices  # climate.ecobee
    assert "00:18:7c:7e:78:0e:cd:86-ae" in devices  # light.no_brightness
    assert "00:78:eb:f8:d5:0c:14:85-e7" in devices  # humidifier.humidifier
    assert "00:67:19:bd:ea:e4:2d:ef-22" in devices  # humidifier.dehumidifier
    assert "00:61:bf:ab:08:b1:a6:18-43" not in devices  # humidifier.hygrostat
    assert "00:62:5c:3e:df:58:40:01-43" in devices  # scene.light_on
    assert "00:1c:72:08:ed:09:e7:89-77" in devices  # scene.light_off

    # Remove the state and ensure it disappears from devices
    hass.states.async_remove("light.ceiling_lights")
    await hass.async_block_till_done()

    result_json = await async_get_lights(hue_client)
    assert "1" not in result_json
    devices = {val["uniqueid"] for val in result_json.values()}
    assert "00:2f:d2:31:ce:c5:55:cc-ee" not in devices  # light.ceiling_lights

    # Restore the state and ensure it reappears in devices
    hass.states.async_set("light.ceiling_lights", STATE_ON)
    await hass.async_block_till_done()
    result_json = await async_get_lights(hue_client)
    device = result_json["1"]  # Test that light ID did not change
    assert device["uniqueid"] == "00:2f:d2:31:ce:c5:55:cc-ee"  # light.ceiling_lights
    assert device["state"][HUE_API_STATE_ON] is True

    # Test that returned value is fresh and not cached
    hass.states.async_set("light.ceiling_lights", STATE_OFF)
    await hass.async_block_till_done()
    result_json = await async_get_lights(hue_client)
    device = result_json["1"]
    assert device["state"][HUE_API_STATE_ON] is False


async def test_light_without_brightness_supported(hass_hue, hue_client) -> None:
    """Test that light without brightness is supported."""
    light_without_brightness_json = await perform_get_light_state(
        hue_client, "light.no_brightness", HTTPStatus.OK
    )

    assert light_without_brightness_json["state"][HUE_API_STATE_ON] is True
    assert light_without_brightness_json["type"] == "On/Off light"


async def test_lights_all_dimmable(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test CONF_LIGHTS_ALL_DIMMABLE."""
    # create a lamp without brightness support
    hass.states.async_set("light.no_brightness", "on", {})
    await setup.async_setup_component(
        hass, http.DOMAIN, {http.DOMAIN: {http.CONF_SERVER_PORT: HTTP_SERVER_PORT}}
    )
    await hass.async_block_till_done()
    hue_config = {
        emulated_hue.CONF_LISTEN_PORT: BRIDGE_SERVER_PORT,
        emulated_hue.CONF_EXPOSE_BY_DEFAULT: True,
        emulated_hue.CONF_LIGHTS_ALL_DIMMABLE: True,
    }
    await _async_setup_emulated_hue(hass, hue_config)
    _mock_hue_endpoints(hass, hue_config, ENTITY_IDS_BY_NUMBER)
    client = await hass_client_no_auth()
    light_without_brightness_json = await perform_get_light_state(
        client, "light.no_brightness", HTTPStatus.OK
    )
    assert light_without_brightness_json["state"][HUE_API_STATE_ON] is True
    assert light_without_brightness_json["type"] == "Dimmable light"
    assert (
        light_without_brightness_json["state"][HUE_API_STATE_BRI]
        == HUE_API_STATE_BRI_MAX
    )


async def test_light_without_brightness_can_be_turned_off(hass_hue, hue_client) -> None:
    """Test that light without brightness can be turned off."""
    hass_hue.states.async_set("light.no_brightness", "on", {})
    turn_off_calls = []

    # Check if light can be turned off
    @callback
    def mock_service_call(call):
        """Mock service call."""
        turn_off_calls.append(call)
        hass_hue.states.async_set("light.no_brightness", "off", {})

    hass_hue.services.async_register(
        light.DOMAIN, SERVICE_TURN_OFF, mock_service_call, schema=None
    )

    no_brightness_result = await perform_put_light_state(
        hass_hue, hue_client, "light.no_brightness", False
    )
    no_brightness_result_json = await no_brightness_result.json()

    assert no_brightness_result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in no_brightness_result.headers["content-type"]
    assert len(no_brightness_result_json) == 1

    # Verify that SERVICE_TURN_OFF has been called
    await hass_hue.async_block_till_done()
    assert len(turn_off_calls) == 1
    call = turn_off_calls[-1]

    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert "light.no_brightness" in call.data[ATTR_ENTITY_ID]


async def test_light_without_brightness_can_be_turned_on(hass_hue, hue_client) -> None:
    """Test that light without brightness can be turned on."""
    hass_hue.states.async_set("light.no_brightness", "off", {})

    # Check if light can be turned on
    turn_on_calls = []

    @callback
    def mock_service_call(call):
        """Mock service call."""
        turn_on_calls.append(call)
        hass_hue.states.async_set("light.no_brightness", "on", {})

    hass_hue.services.async_register(
        light.DOMAIN, SERVICE_TURN_ON, mock_service_call, schema=None
    )

    no_brightness_result = await perform_put_light_state(
        hass_hue,
        hue_client,
        "light.no_brightness",
        True,
        # Some remotes, like HarmonyHub send brightness value regardless of light's features
        brightness=0,
    )

    no_brightness_result_json = await no_brightness_result.json()

    assert no_brightness_result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in no_brightness_result.headers["content-type"]
    assert len(no_brightness_result_json) == 1

    # Verify that SERVICE_TURN_ON has been called
    await hass_hue.async_block_till_done()
    assert len(turn_on_calls) == 1
    call = turn_on_calls[-1]

    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert "light.no_brightness" in call.data[ATTR_ENTITY_ID]


@pytest.mark.parametrize(
    ("state", "is_reachable"),
    [
        (const.STATE_UNAVAILABLE, False),
        (const.STATE_OK, True),
        (const.STATE_UNKNOWN, True),
    ],
)
async def test_reachable_for_state(hass_hue, hue_client, state, is_reachable) -> None:
    """Test that an entity is reported as unreachable if in unavailable state."""
    entity_id = "light.ceiling_lights"

    hass_hue.states.async_set(entity_id, state)

    state_json = await perform_get_light_state(hue_client, entity_id, HTTPStatus.OK)

    assert state_json["state"]["reachable"] == is_reachable, state_json


async def test_discover_full_state(hue_client) -> None:
    """Test the discovery of full state."""
    result = await hue_client.get(f"/api/{HUE_API_USERNAME}")

    assert result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in result.headers["content-type"]

    result_json = await result.json()

    # Make sure array has correct content
    assert "lights" in result_json
    assert "lights" not in result_json["config"]
    assert "config" in result_json
    assert "config" not in result_json["lights"]

    lights_json = result_json["lights"]
    config_json = result_json["config"]

    # Make sure array is correct size
    assert len(result_json) == 2
    assert len(config_json) == 7
    assert len(lights_json) >= 1
    assert "name" in config_json

    # Make sure the config wrapper added to the config is there
    assert "mac" in config_json
    assert "00:00:00:00:00:00" in config_json["mac"]

    # Make sure the correct version in config
    assert "swversion" in config_json
    assert "01003542" in config_json["swversion"]

    # Make sure the api version is correct
    assert "apiversion" in config_json
    assert "1.17.0" in config_json["apiversion"]

    # Make sure the correct username in config
    assert "whitelist" in config_json
    assert HUE_API_USERNAME in config_json["whitelist"]
    assert "name" in config_json["whitelist"][HUE_API_USERNAME]
    assert "HASS BRIDGE" in config_json["whitelist"][HUE_API_USERNAME]["name"]

    # Make sure the correct ip in config
    assert "ipaddress" in config_json
    assert "127.0.0.1:8300" in config_json["ipaddress"]

    # Make sure the device announces a link button
    assert "linkbutton" in config_json
    assert config_json["linkbutton"] is True


async def test_discover_config(hue_client) -> None:
    """Test the discovery of configuration."""
    result = await hue_client.get(f"/api/{HUE_API_USERNAME}/config")

    assert result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in result.headers["content-type"]

    config_json = await result.json()

    # Make sure array is correct size
    assert len(config_json) == 7
    assert "name" in config_json

    # Make sure the config wrapper added to the config is there
    assert "mac" in config_json
    assert "00:00:00:00:00:00" in config_json["mac"]

    # Make sure the correct version in config
    assert "swversion" in config_json
    assert "01003542" in config_json["swversion"]

    # Make sure the api version is correct
    assert "apiversion" in config_json
    assert "1.17.0" in config_json["apiversion"]

    # Make sure the correct username in config
    assert "whitelist" in config_json
    assert HUE_API_USERNAME in config_json["whitelist"]
    assert "name" in config_json["whitelist"][HUE_API_USERNAME]
    assert "HASS BRIDGE" in config_json["whitelist"][HUE_API_USERNAME]["name"]

    # Make sure the correct ip in config
    assert "ipaddress" in config_json
    assert "127.0.0.1:8300" in config_json["ipaddress"]

    # Make sure the device announces a link button
    assert "linkbutton" in config_json
    assert config_json["linkbutton"] is True

    # Test without username
    result = await hue_client.get("/api/config")

    assert result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in result.headers["content-type"]

    config_json = await result.json()
    assert "error" not in config_json

    # Test with wrong username username
    result = await hue_client.get("/api/wronguser/config")

    assert result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in result.headers["content-type"]

    config_json = await result.json()
    assert "error" not in config_json


async def test_get_light_state(hass_hue, hue_client) -> None:
    """Test the getting of light state."""
    # Turn ceiling lights on and set to 127 brightness, and set light color
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_ON,
        {
            const.ATTR_ENTITY_ID: "light.ceiling_lights",
            light.ATTR_BRIGHTNESS: 127,
            light.ATTR_RGB_COLOR: (1, 2, 7),
        },
        blocking=True,
    )

    office_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTPStatus.OK
    )

    assert office_json["state"][HUE_API_STATE_ON] is True
    assert office_json["state"][HUE_API_STATE_BRI] == 127
    assert office_json["state"][HUE_API_STATE_HUE] == 41869
    assert office_json["state"][HUE_API_STATE_SAT] == 217

    # Check all lights view
    result_json = await async_get_lights(hue_client)
    assert ENTITY_NUMBERS_BY_ID["light.ceiling_lights"] in result_json
    assert (
        result_json[ENTITY_NUMBERS_BY_ID["light.ceiling_lights"]]["state"][
            HUE_API_STATE_BRI
        ]
        == 127
    )

    # Turn office light off
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: "light.ceiling_lights"},
        blocking=True,
    )

    office_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTPStatus.OK
    )

    assert office_json["state"][HUE_API_STATE_ON] is False
    # Removed assert HUE_API_STATE_BRI == 0 as Hue API states bri must be 1..254
    assert office_json["state"][HUE_API_STATE_HUE] == 0
    assert office_json["state"][HUE_API_STATE_SAT] == 0

    # Make sure bedroom light isn't accessible
    await perform_get_light_state(
        hue_client, "light.bed_light", HTTPStatus.UNAUTHORIZED
    )

    # Make sure kitchen light isn't accessible
    await perform_get_light_state(
        hue_client, "light.kitchen_lights", HTTPStatus.UNAUTHORIZED
    )


async def test_put_light_state(hass: HomeAssistant, hass_hue, hue_client) -> None:
    """Test the setting of light states."""
    await perform_put_test_on_ceiling_lights(hass_hue, hue_client)

    # Turn the bedroom light on first
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_ON,
        {const.ATTR_ENTITY_ID: "light.ceiling_lights", light.ATTR_BRIGHTNESS: 153},
        blocking=True,
    )

    ceiling_lights = hass_hue.states.get("light.ceiling_lights")
    assert ceiling_lights.state == STATE_ON
    assert ceiling_lights.attributes[light.ATTR_BRIGHTNESS] == 153

    # update light state through api
    await perform_put_light_state(
        hass_hue,
        hue_client,
        "light.ceiling_lights",
        True,
        hue=4369,
        saturation=127,
        brightness=128,
    )

    assert (
        hass.states.get("light.ceiling_lights").attributes[light.ATTR_BRIGHTNESS] == 129
    )

    # update light state through api
    await perform_put_light_state(
        hass_hue,
        hue_client,
        "light.ceiling_lights",
        True,
        hue=4369,
        saturation=127,
        brightness=123,
    )

    assert (
        hass.states.get("light.ceiling_lights").attributes[light.ATTR_BRIGHTNESS] == 123
    )

    # go through api to get the state back
    ceiling_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTPStatus.OK
    )
    assert ceiling_json["state"][HUE_API_STATE_BRI] == 123
    assert ceiling_json["state"][HUE_API_STATE_HUE] == 4369
    assert ceiling_json["state"][HUE_API_STATE_SAT] == 127

    # update light state through api
    await perform_put_light_state(
        hass_hue,
        hue_client,
        "light.ceiling_lights",
        True,
        hue=4369,
        saturation=127,
        brightness=255,
    )

    # go through api to get the state back
    ceiling_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTPStatus.OK
    )
    assert ceiling_json["state"][HUE_API_STATE_BRI] == 254
    assert ceiling_json["state"][HUE_API_STATE_HUE] == 4369
    assert ceiling_json["state"][HUE_API_STATE_SAT] == 127

    # update light state through api
    await perform_put_light_state(
        hass_hue,
        hue_client,
        "light.ceiling_lights",
        True,
        brightness=100,
        xy=((0.488, 0.48)),
    )

    # go through api to get the state back
    ceiling_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTPStatus.OK
    )
    assert ceiling_json["state"][HUE_API_STATE_BRI] == 100
    assert hass.states.get("light.ceiling_lights").attributes[light.ATTR_XY_COLOR] == (
        (0.488, 0.48)
    )

    # Go through the API to turn it off
    ceiling_result = await perform_put_light_state(
        hass_hue, hue_client, "light.ceiling_lights", False
    )

    ceiling_result_json = await ceiling_result.json()

    assert ceiling_result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in ceiling_result.headers["content-type"]

    assert len(ceiling_result_json) == 1

    # Check to make sure the state changed
    ceiling_lights = hass_hue.states.get("light.ceiling_lights")
    assert ceiling_lights.state == STATE_OFF
    ceiling_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTPStatus.OK
    )
    # Removed assert HUE_API_STATE_BRI == 0 as Hue API states bri must be 1..254
    assert ceiling_json["state"][HUE_API_STATE_HUE] == 0
    assert ceiling_json["state"][HUE_API_STATE_SAT] == 0

    # Make sure we can't change the bedroom light state
    bedroom_result = await perform_put_light_state(
        hass_hue, hue_client, "light.bed_light", True
    )
    assert bedroom_result.status == HTTPStatus.UNAUTHORIZED

    # Make sure we can't change the kitchen light state
    kitchen_result = await perform_put_light_state(
        hass_hue, hue_client, "light.kitchen_lights", True
    )
    assert kitchen_result.status == HTTPStatus.UNAUTHORIZED

    # Turn the ceiling lights on first and color temp.
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_ON,
        {const.ATTR_ENTITY_ID: "light.ceiling_lights", light.ATTR_COLOR_TEMP: 20},
        blocking=True,
    )

    await perform_put_light_state(
        hass_hue, hue_client, "light.ceiling_lights", True, color_temp=50
    )

    assert (
        hass_hue.states.get("light.ceiling_lights").attributes[light.ATTR_COLOR_TEMP]
        == 50
    )

    # mock light.turn_on call
    attributes = hass.states.get("light.ceiling_lights").attributes
    supported_features = attributes[ATTR_SUPPORTED_FEATURES] | light.SUPPORT_TRANSITION
    attributes = {**attributes, ATTR_SUPPORTED_FEATURES: supported_features}
    hass.states.async_set("light.ceiling_lights", STATE_ON, attributes)
    call_turn_on = async_mock_service(hass, "light", "turn_on")

    # update light state through api
    await perform_put_light_state(
        hass_hue,
        hue_client,
        "light.ceiling_lights",
        True,
        brightness=99,
        xy=((0.488, 0.48)),
        transitiontime=60,
    )

    await hass.async_block_till_done()
    assert call_turn_on[0]
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == ["light.ceiling_lights"]
    assert call_turn_on[0].data[light.ATTR_BRIGHTNESS] == 99
    assert call_turn_on[0].data[light.ATTR_XY_COLOR] == ((0.488, 0.48))
    assert call_turn_on[0].data[light.ATTR_TRANSITION] == 6


async def test_put_light_state_script(
    hass: HomeAssistant, hass_hue, hue_client
) -> None:
    """Test the setting of script variables."""
    # Turn the kitchen light off first
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: "light.kitchen_lights"},
        blocking=True,
    )

    # Emulated hue converts 0-100% to 0-254.
    level = 23
    brightness = round(level * 254 / 100)

    script_result = await perform_put_light_state(
        hass_hue, hue_client, "script.set_kitchen_light", True, brightness
    )

    script_result_json = await script_result.json()

    assert script_result.status == HTTPStatus.OK
    assert len(script_result_json) == 2

    kitchen_light = hass_hue.states.get("light.kitchen_lights")
    assert kitchen_light.state == "on"
    assert kitchen_light.attributes[light.ATTR_BRIGHTNESS] == level

    assert (
        hass.states.get("light.kitchen_lights").attributes[light.ATTR_BRIGHTNESS] == 23
    )


async def test_put_light_state_climate_set_temperature(hass_hue, hue_client) -> None:
    """Test setting climate temperature."""
    brightness = 19
    temperature = round(brightness / 254 * 100)

    hvac_result = await perform_put_light_state(
        hass_hue, hue_client, "climate.hvac", True, brightness
    )

    hvac_result_json = await hvac_result.json()

    assert hvac_result.status == HTTPStatus.OK
    assert len(hvac_result_json) == 2

    hvac = hass_hue.states.get("climate.hvac")
    assert hvac.state == climate.HVACMode.COOL
    assert hvac.attributes[climate.ATTR_TEMPERATURE] == temperature

    # Make sure we can't change the ecobee temperature since it's not exposed
    ecobee_result = await perform_put_light_state(
        hass_hue, hue_client, "climate.ecobee", True
    )
    assert ecobee_result.status == HTTPStatus.UNAUTHORIZED


async def test_put_light_state_humidifier_set_humidity(hass_hue, hue_client) -> None:
    """Test setting humidifier target humidity."""
    # Turn the humidifier off first
    await hass_hue.services.async_call(
        humidifier.DOMAIN,
        const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: "humidifier.humidifier"},
        blocking=True,
    )

    brightness = 19
    humidity = round(brightness / 254 * 100)

    humidifier_result = await perform_put_light_state(
        hass_hue, hue_client, "humidifier.humidifier", True, brightness
    )

    humidifier_result_json = await humidifier_result.json()

    assert humidifier_result.status == HTTPStatus.OK
    assert len(humidifier_result_json) == 2

    hvac = hass_hue.states.get("humidifier.humidifier")
    assert hvac.state == "on"
    assert hvac.attributes[humidifier.ATTR_HUMIDITY] == humidity

    # Make sure we can't change the hygrostat humidity since it's not exposed
    hygrostat_result = await perform_put_light_state(
        hass_hue, hue_client, "humidifier.hygrostat", True
    )
    assert hygrostat_result.status == HTTPStatus.UNAUTHORIZED


async def test_put_light_state_media_player(hass_hue, hue_client) -> None:
    """Test turning on media player and setting volume."""
    # Turn the music player off first
    await hass_hue.services.async_call(
        media_player.DOMAIN,
        const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: "media_player.walkman"},
        blocking=True,
    )

    # Emulated hue converts 0.0-1.0 to 0-254.
    level = 0.25
    brightness = round(level * 254)

    mp_result = await perform_put_light_state(
        hass_hue, hue_client, "media_player.walkman", True, brightness
    )

    mp_result_json = await mp_result.json()

    assert mp_result.status == HTTPStatus.OK
    assert len(mp_result_json) == 2

    walkman = hass_hue.states.get("media_player.walkman")
    assert walkman.state == "playing"
    assert walkman.attributes[media_player.ATTR_MEDIA_VOLUME_LEVEL] == level


async def test_open_cover_without_position(hass_hue, hue_client) -> None:
    """Test opening cover ."""
    cover_id = "cover.living_room_window"
    # Close cover first
    await hass_hue.services.async_call(
        cover.DOMAIN,
        const.SERVICE_CLOSE_COVER,
        {const.ATTR_ENTITY_ID: cover_id},
        blocking=True,
    )

    cover_test = hass_hue.states.get(cover_id)
    assert cover_test.state == "closing"

    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass_hue, future)
        await hass_hue.async_block_till_done()

    cover_test = hass_hue.states.get(cover_id)
    assert cover_test.state == "closed"

    # Go through the API to turn it on
    cover_result = await perform_put_light_state(hass_hue, hue_client, cover_id, True)

    assert cover_result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in cover_result.headers["content-type"]

    for _ in range(11):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass_hue, future)
        await hass_hue.async_block_till_done()

    cover_result_json = await cover_result.json()

    assert len(cover_result_json) == 1

    # Check to make sure the state changed
    cover_test_2 = hass_hue.states.get(cover_id)
    assert cover_test_2.state == "open"
    assert cover_test_2.attributes.get("current_position") == 100

    # Go through the API to turn it off
    cover_result = await perform_put_light_state(hass_hue, hue_client, cover_id, False)

    assert cover_result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in cover_result.headers["content-type"]

    for _ in range(11):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass_hue, future)
        await hass_hue.async_block_till_done()

    cover_result_json = await cover_result.json()

    assert len(cover_result_json) == 1

    # Check to make sure the state changed
    cover_test_2 = hass_hue.states.get(cover_id)
    assert cover_test_2.state == "closed"
    assert cover_test_2.attributes.get("current_position") == 0


async def test_set_position_cover(hass_hue, hue_client) -> None:
    """Test setting position cover ."""
    cover_id = "cover.living_room_window"
    cover_number = ENTITY_NUMBERS_BY_ID[cover_id]
    # Turn the office light off first
    await hass_hue.services.async_call(
        cover.DOMAIN,
        const.SERVICE_CLOSE_COVER,
        {const.ATTR_ENTITY_ID: cover_id},
        blocking=True,
    )

    cover_test = hass_hue.states.get(cover_id)
    assert cover_test.state == "closing"

    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass_hue, future)
        await hass_hue.async_block_till_done()

    cover_test = hass_hue.states.get(cover_id)
    assert cover_test.state == "closed"

    cover_json = await perform_get_light_state(
        hue_client, "cover.living_room_window", HTTPStatus.OK
    )
    assert cover_json["state"][HUE_API_STATE_ON] is False
    assert cover_json["state"][HUE_API_STATE_BRI] == 1

    level = 20
    brightness = round(level / 100 * 254)

    # Go through the API to open
    cover_result = await perform_put_light_state(
        hass_hue, hue_client, cover_id, False, brightness
    )

    assert cover_result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in cover_result.headers["content-type"]

    cover_result_json = await cover_result.json()

    assert len(cover_result_json) == 2
    assert True, cover_result_json[0]["success"][f"/lights/{cover_number}/state/on"]
    assert cover_result_json[1]["success"][f"/lights/{cover_number}/state/bri"] == level

    for _ in range(100):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass_hue, future)
        await hass_hue.async_block_till_done()

    # Check to make sure the state changed
    cover_test_2 = hass_hue.states.get(cover_id)
    assert cover_test_2.state == "open"
    assert cover_test_2.attributes.get("current_position") == level


async def test_put_light_state_fan(hass_hue, hue_client) -> None:
    """Test turning on fan and setting speed."""
    # Turn the fan off first
    await hass_hue.services.async_call(
        fan.DOMAIN,
        const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: "fan.living_room_fan"},
        blocking=True,
    )

    # Emulated hue converts 0-100% to 0-254.
    level = 43
    brightness = round(level * 254 / 100)

    fan_result = await perform_put_light_state(
        hass_hue, hue_client, "fan.living_room_fan", True, brightness
    )

    fan_result_json = await fan_result.json()

    assert fan_result.status == HTTPStatus.OK
    assert len(fan_result_json) == 2

    living_room_fan = hass_hue.states.get("fan.living_room_fan")
    assert living_room_fan.state == "on"
    assert living_room_fan.attributes[fan.ATTR_PERCENTAGE] == 43

    # Check setting the brightness of a fan to 0, 33%, 66% and 100% will respectively turn it off, low, medium or high
    # We also check non-cached GET value to exercise the code.
    await perform_put_light_state(
        hass_hue, hue_client, "fan.living_room_fan", True, brightness=0
    )
    assert hass_hue.states.get("fan.living_room_fan").state == STATE_OFF
    await perform_put_light_state(
        hass_hue,
        hue_client,
        "fan.living_room_fan",
        True,
        brightness=round(33 * 254 / 100),
    )
    assert (
        hass_hue.states.get("fan.living_room_fan").attributes[fan.ATTR_PERCENTAGE] == 33
    )
    with patch.object(hue_api, "STATE_CACHED_TIMEOUT", 0.000001):
        await asyncio.sleep(0.000001)
        fan_json = await perform_get_light_state(
            hue_client, "fan.living_room_fan", HTTPStatus.OK
        )
        assert fan_json["state"][HUE_API_STATE_ON] is True
        assert round(fan_json["state"][HUE_API_STATE_BRI] * 100 / 254) == 33

    await perform_put_light_state(
        hass_hue,
        hue_client,
        "fan.living_room_fan",
        True,
        brightness=round(66 * 254 / 100),
    )
    assert (
        hass_hue.states.get("fan.living_room_fan").attributes[fan.ATTR_PERCENTAGE] == 66
    )
    with patch.object(hue_api, "STATE_CACHED_TIMEOUT", 0.000001):
        await asyncio.sleep(0.000001)
        fan_json = await perform_get_light_state(
            hue_client, "fan.living_room_fan", HTTPStatus.OK
        )
        assert fan_json["state"][HUE_API_STATE_ON] is True
        assert (
            round(fan_json["state"][HUE_API_STATE_BRI] * 100 / 254) == 66
        )  # small rounding error in inverse operation

    await perform_put_light_state(
        hass_hue,
        hue_client,
        "fan.living_room_fan",
        True,
        brightness=round(100 * 254 / 100),
    )
    assert (
        hass_hue.states.get("fan.living_room_fan").attributes[fan.ATTR_PERCENTAGE]
        == 100
    )
    with patch.object(hue_api, "STATE_CACHED_TIMEOUT", 0.000001):
        await asyncio.sleep(0.000001)
        fan_json = await perform_get_light_state(
            hue_client, "fan.living_room_fan", HTTPStatus.OK
        )
        assert fan_json["state"][HUE_API_STATE_ON] is True
        assert round(fan_json["state"][HUE_API_STATE_BRI] * 100 / 254) == 100

    await perform_put_light_state(
        hass_hue,
        hue_client,
        "fan.living_room_fan",
        False,
        brightness=0,
    )
    assert (
        hass_hue.states.get("fan.living_room_fan").attributes[fan.ATTR_PERCENTAGE] == 0
    )
    with patch.object(hue_api, "STATE_CACHED_TIMEOUT", 0.000001):
        await asyncio.sleep(0.000001)
        fan_json = await perform_get_light_state(
            hue_client, "fan.living_room_fan", HTTPStatus.OK
        )
        assert fan_json["state"][HUE_API_STATE_ON] is False
        assert fan_json["state"][HUE_API_STATE_BRI] == 1


async def test_put_with_form_urlencoded_content_type(hass_hue, hue_client) -> None:
    """Test the form with urlencoded content."""
    entity_number = ENTITY_NUMBERS_BY_ID["light.ceiling_lights"]
    # Needed for Alexa
    await perform_put_test_on_ceiling_lights(
        hass_hue, hue_client, "application/x-www-form-urlencoded"
    )

    # Make sure we fail gracefully when we can't parse the data
    data = {"key1": "value1", "key2": "value2"}
    result = await hue_client.put(
        f"/api/username/lights/{entity_number}/state",
        headers={"content-type": "application/x-www-form-urlencoded"},
        data=data,
    )

    assert result.status == HTTPStatus.BAD_REQUEST


async def test_entity_not_found(hue_client) -> None:
    """Test for entity which are not found."""
    result = await hue_client.get("/api/username/lights/98")

    assert result.status == HTTPStatus.NOT_FOUND

    result = await hue_client.put("/api/username/lights/98/state")

    assert result.status == HTTPStatus.NOT_FOUND


async def test_allowed_methods(hue_client) -> None:
    """Test the allowed methods."""
    result = await hue_client.get(
        "/api/username/lights/ENTITY_NUMBERS_BY_ID[light.ceiling_lights]/state"
    )

    assert result.status == HTTPStatus.METHOD_NOT_ALLOWED

    result = await hue_client.put(
        "/api/username/lights/ENTITY_NUMBERS_BY_ID[light.ceiling_lights]"
    )

    assert result.status == HTTPStatus.METHOD_NOT_ALLOWED

    result = await hue_client.put("/api/username/lights")

    assert result.status == HTTPStatus.METHOD_NOT_ALLOWED


async def test_proper_put_state_request(hue_client) -> None:
    """Test the request to set the state."""
    # Test proper on value parsing
    result = await hue_client.put(
        "/api/username/lights/{}/state".format(
            ENTITY_NUMBERS_BY_ID["light.ceiling_lights"]
        ),
        data=json.dumps({HUE_API_STATE_ON: 1234}),
    )

    assert result.status == HTTPStatus.BAD_REQUEST

    # Test proper brightness value parsing
    result = await hue_client.put(
        "/api/username/lights/{}/state".format(
            ENTITY_NUMBERS_BY_ID["light.ceiling_lights"]
        ),
        data=json.dumps({HUE_API_STATE_ON: True, HUE_API_STATE_BRI: "Hello world!"}),
    )

    assert result.status == HTTPStatus.BAD_REQUEST


async def test_get_empty_groups_state(hue_client) -> None:
    """Test the request to get groups endpoint."""
    # Test proper on value parsing
    result = await hue_client.get("/api/username/groups")

    assert result.status == HTTPStatus.OK

    result_json = await result.json()

    assert result_json == {}


async def perform_put_test_on_ceiling_lights(
    hass_hue, hue_client, content_type=CONTENT_TYPE_JSON
):
    """Test the setting of a light."""
    # Turn the office light off first
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: "light.ceiling_lights"},
        blocking=True,
    )

    ceiling_lights = hass_hue.states.get("light.ceiling_lights")
    assert ceiling_lights.state == STATE_OFF

    # Go through the API to turn it on
    office_result = await perform_put_light_state(
        hass_hue, hue_client, "light.ceiling_lights", True, 56, content_type
    )

    assert office_result.status == HTTPStatus.OK
    assert CONTENT_TYPE_JSON in office_result.headers["content-type"]

    office_result_json = await office_result.json()

    assert len(office_result_json) == 2

    # Check to make sure the state changed
    ceiling_lights = hass_hue.states.get("light.ceiling_lights")
    assert ceiling_lights.state == STATE_ON
    assert ceiling_lights.attributes[light.ATTR_BRIGHTNESS] == 56


async def perform_get_light_state_by_number(client, entity_number, expected_status):
    """Test the getting of a light state."""
    result = await client.get(f"/api/username/lights/{entity_number}")

    assert result.status == expected_status

    if expected_status == HTTPStatus.OK:
        assert CONTENT_TYPE_JSON in result.headers["content-type"]

        return await result.json()

    return None


async def perform_get_light_state(client, entity_id, expected_status):
    """Test the getting of a light state."""
    entity_number = ENTITY_NUMBERS_BY_ID[entity_id]
    return await perform_get_light_state_by_number(
        client, entity_number, expected_status
    )


async def perform_put_light_state(
    hass_hue,
    client,
    entity_id,
    is_on,
    brightness=None,
    content_type=CONTENT_TYPE_JSON,
    hue=None,
    saturation=None,
    color_temp=None,
    with_state=True,
    xy=None,
    transitiontime=None,
):
    """Test the setting of a light state."""
    req_headers = {"Content-Type": content_type}

    data = {}

    if with_state:
        data[HUE_API_STATE_ON] = is_on

    if brightness is not None:
        data[HUE_API_STATE_BRI] = brightness
    if hue is not None:
        data[HUE_API_STATE_HUE] = hue
    if saturation is not None:
        data[HUE_API_STATE_SAT] = saturation
    if xy is not None:
        data[HUE_API_STATE_XY] = xy
    if color_temp is not None:
        data[HUE_API_STATE_CT] = color_temp
    if transitiontime is not None:
        data[HUE_API_STATE_TRANSITION] = transitiontime

    entity_number = ENTITY_NUMBERS_BY_ID[entity_id]
    result = await client.put(
        f"/api/username/lights/{entity_number}/state",
        headers=req_headers,
        data=json.dumps(data).encode(),
    )

    # Wait until state change is complete before continuing
    await hass_hue.async_block_till_done()

    return result


async def test_external_ip_blocked(hue_client) -> None:
    """Test external IP blocked."""
    getUrls = [
        "/api/username/groups",
        "/api/username",
        "/api/username/config",
        "/api/username/lights",
        "/api/username/lights/light.ceiling_lights",
    ]
    postUrls = ["/api"]
    putUrls = [
        "/api/username/lights/light.ceiling_lights/state",
        "/api/username/groups/0/action",
    ]
    with patch(
        "homeassistant.components.emulated_hue.hue_api.ip_address",
        return_value=ip_address("45.45.45.45"),
    ):
        for getUrl in getUrls:
            _remote_is_allowed.cache_clear()
            result = await hue_client.get(getUrl)
            assert result.status == HTTPStatus.UNAUTHORIZED

        for postUrl in postUrls:
            _remote_is_allowed.cache_clear()
            result = await hue_client.post(postUrl)
            assert result.status == HTTPStatus.UNAUTHORIZED

        for putUrl in putUrls:
            _remote_is_allowed.cache_clear()
            result = await hue_client.put(putUrl)
            assert result.status == HTTPStatus.UNAUTHORIZED

    # We are patching inside of a cache so be sure to clear it
    # so that the next test is not affected
    _remote_is_allowed.cache_clear()


async def test_unauthorized_user_blocked(hue_client) -> None:
    """Test unauthorized_user blocked."""
    getUrls = [
        "/api/wronguser",
    ]
    for getUrl in getUrls:
        result = await hue_client.get(getUrl)
        assert result.status == HTTPStatus.OK

        result_json = await result.json()
        assert result_json[0]["error"]["description"] == "unauthorized user"


async def test_put_then_get_cached_properly(
    hass: HomeAssistant, hass_hue, hue_client
) -> None:
    """Test the setting of light states and an immediate readback reads the same values."""

    # Turn the bedroom light on first
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_ON,
        {const.ATTR_ENTITY_ID: "light.ceiling_lights", light.ATTR_BRIGHTNESS: 153},
        blocking=True,
    )

    ceiling_lights = hass_hue.states.get("light.ceiling_lights")
    assert ceiling_lights.state == STATE_ON
    assert ceiling_lights.attributes[light.ATTR_BRIGHTNESS] == 153

    # update light state through api
    await perform_put_light_state(
        hass_hue,
        hue_client,
        "light.ceiling_lights",
        True,
        hue=4369,
        saturation=127,
        brightness=254,
    )

    # Check that a Hue brightness level of 254 becomes 255 in HA realm.
    assert (
        hass.states.get("light.ceiling_lights").attributes[light.ATTR_BRIGHTNESS] == 255
    )

    # Make sure that the GET response is the same as the PUT response within 2 seconds if the service call is successful and the state doesn't change.
    # We simulate a long latence for the actual setting of the entity by forcibly sitting different values directly.
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_ON,
        {const.ATTR_ENTITY_ID: "light.ceiling_lights", light.ATTR_BRIGHTNESS: 153},
        blocking=True,
    )

    # go through api to get the state back, the value returned should match those set in the last PUT request.
    ceiling_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTPStatus.OK
    )

    assert ceiling_json["state"][HUE_API_STATE_HUE] == 4369
    assert ceiling_json["state"][HUE_API_STATE_SAT] == 127
    assert ceiling_json["state"][HUE_API_STATE_BRI] == 254

    # Make sure that the GET response does not use the cache if PUT response within 2 seconds if the service call is Unsuccessful and the state does not change.
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: "light.ceiling_lights"},
        blocking=True,
    )

    # go through api to get the state back
    ceiling_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTPStatus.OK
    )

    # Now it should be the real value as the state of the entity has changed to OFF.
    assert ceiling_json["state"][HUE_API_STATE_HUE] == 0
    assert ceiling_json["state"][HUE_API_STATE_SAT] == 0
    assert ceiling_json["state"][HUE_API_STATE_BRI] == 1

    # Ensure we read the actual value after exceeding the timeout time.

    # Turn the bedroom light back on first
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_ON,
        {const.ATTR_ENTITY_ID: "light.ceiling_lights"},
        blocking=True,
    )

    # update light state through api
    await perform_put_light_state(
        hass_hue,
        hue_client,
        "light.ceiling_lights",
        True,
        hue=4369,
        saturation=127,
        brightness=254,
    )

    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_ON,
        {
            const.ATTR_ENTITY_ID: "light.ceiling_lights",
            light.ATTR_BRIGHTNESS: 127,
            light.ATTR_RGB_COLOR: (1, 2, 7),
        },
        blocking=True,
    )

    # go through api to get the state back, the value returned should match those set in the last PUT request.
    ceiling_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTPStatus.OK
    )

    # With no wait, we must be reading what we set via the PUT call.
    assert ceiling_json["state"][HUE_API_STATE_HUE] == 4369
    assert ceiling_json["state"][HUE_API_STATE_SAT] == 127
    assert ceiling_json["state"][HUE_API_STATE_BRI] == 254

    with patch.object(hue_api, "STATE_CACHED_TIMEOUT", 0.000001):
        await asyncio.sleep(0.000001)

        # go through api to get the state back, the value returned should now match the actual values.
        ceiling_json = await perform_get_light_state(
            hue_client, "light.ceiling_lights", HTTPStatus.OK
        )

        # Once we're after the cached duration, we should see the real value.
        assert ceiling_json["state"][HUE_API_STATE_HUE] == 41869
        assert ceiling_json["state"][HUE_API_STATE_SAT] == 217
        assert ceiling_json["state"][HUE_API_STATE_BRI] == 127


async def test_put_than_get_when_service_call_fails(
    hass: HomeAssistant, hass_hue, hue_client
) -> None:
    """Test putting and getting the light state when the service call fails."""

    # Turn the bedroom light off first
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: "light.ceiling_lights"},
        blocking=True,
    )

    turn_on_calls = []

    # Now break the turn on service
    @callback
    def mock_service_call(call):
        """Mock service call."""
        turn_on_calls.append(call)

    hass_hue.services.async_register(
        light.DOMAIN, SERVICE_TURN_ON, mock_service_call, schema=None
    )

    ceiling_lights = hass_hue.states.get("light.ceiling_lights")
    assert ceiling_lights.state == STATE_OFF

    with patch.object(hue_api, "STATE_CHANGE_WAIT_TIMEOUT", 0.000001):
        # update light state through api
        await perform_put_light_state(
            hass_hue,
            hue_client,
            "light.ceiling_lights",
            True,
            hue=4369,
            saturation=127,
            brightness=254,
        )

    # Ensure we did not actually turn on
    assert hass.states.get("light.ceiling_lights").state == STATE_OFF

    # go through api to get the state back, the value returned should NOT match those set in the last PUT request
    # as the waiting to check the state change timed out
    ceiling_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTPStatus.OK
    )

    assert ceiling_json["state"][HUE_API_STATE_ON] is False


async def test_get_invalid_entity(hass: HomeAssistant, hass_hue, hue_client) -> None:
    """Test the setting of light states and an immediate readback reads the same values."""

    # Check that we get an error with an invalid entity number.
    await perform_get_light_state_by_number(hue_client, 999, HTTPStatus.NOT_FOUND)


async def test_put_light_state_scene(hass: HomeAssistant, hass_hue, hue_client) -> None:
    """Test the setting of scene variables."""
    # Turn the kitchen lights off first
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: "light.kitchen_lights"},
        blocking=True,
    )

    scene_result = await perform_put_light_state(
        hass_hue, hue_client, "scene.light_on", True
    )

    scene_result_json = await scene_result.json()
    assert scene_result.status == HTTPStatus.OK
    assert len(scene_result_json) == 1

    assert hass_hue.states.get("light.kitchen_lights").state == STATE_ON

    # Set the brightness on the entity; changing a scene brightness via the hue API will do nothing.
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_ON,
        {const.ATTR_ENTITY_ID: "light.kitchen_lights", light.ATTR_BRIGHTNESS: 127},
        blocking=True,
    )

    await perform_put_light_state(
        hass_hue, hue_client, "scene.light_on", True, brightness=254
    )

    assert hass_hue.states.get("light.kitchen_lights").state == STATE_ON
    assert (
        hass_hue.states.get("light.kitchen_lights").attributes[light.ATTR_BRIGHTNESS]
        == 127
    )

    await perform_put_light_state(hass_hue, hue_client, "scene.light_off", True)
    assert hass_hue.states.get("light.kitchen_lights").state == STATE_OFF


async def test_only_change_contrast(hass: HomeAssistant, hass_hue, hue_client) -> None:
    """Test when only changing the contrast of a light state."""

    # Turn the kitchen lights off first
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: "light.ceiling_lights"},
        blocking=True,
    )

    await perform_put_light_state(
        hass_hue,
        hue_client,
        "light.ceiling_lights",
        True,
        brightness=254,
        with_state=False,
    )

    # Check that only setting the contrast will also turn on the light.
    # TODO: It should be noted that a real Hue hub will not allow to change the brightness if the underlying entity is off.
    # giving the error: [{"error":{"type":201,"address":"/lights/20/state/bri","description":"parameter, bri, is not modifiable. Device is set to off."}}]
    # emulated_hue however will always turn on the light.
    ceiling_lights = hass_hue.states.get("light.ceiling_lights")
    assert ceiling_lights.state == STATE_ON
    assert ceiling_lights.attributes[light.ATTR_BRIGHTNESS] == 255


async def test_only_change_hue_or_saturation(
    hass: HomeAssistant, hass_hue, hue_client
) -> None:
    """Test setting either the hue or the saturation but not both."""

    # TODO: The handling of this appears wrong, as setting only one will set the other to 0.
    # The return values also appear wrong.

    # Turn the ceiling lights on first and set hue and saturation.
    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_ON,
        {const.ATTR_ENTITY_ID: "light.ceiling_lights", light.ATTR_HS_COLOR: (10, 10)},
        blocking=True,
    )

    await perform_put_light_state(
        hass_hue, hue_client, "light.ceiling_lights", True, hue=4369
    )

    assert hass_hue.states.get("light.ceiling_lights").attributes[
        light.ATTR_HS_COLOR
    ] == (24, 0)

    await hass_hue.services.async_call(
        light.DOMAIN,
        const.SERVICE_TURN_ON,
        {const.ATTR_ENTITY_ID: "light.ceiling_lights", light.ATTR_HS_COLOR: (10, 10)},
        blocking=True,
    )
    await perform_put_light_state(
        hass_hue, hue_client, "light.ceiling_lights", True, saturation=10
    )

    assert hass_hue.states.get("light.ceiling_lights").attributes[
        light.ATTR_HS_COLOR
    ] == (0, 3)


async def test_specificly_exposed_entities(
    hass: HomeAssistant, base_setup, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test specific entities with expose by default off."""
    conf = {
        emulated_hue.CONF_LISTEN_PORT: BRIDGE_SERVER_PORT,
        emulated_hue.CONF_EXPOSE_BY_DEFAULT: False,
        emulated_hue.CONF_ENTITIES: {
            "light.exposed": {emulated_hue.CONF_ENTITY_HIDDEN: False},
        },
    }
    await _async_setup_emulated_hue(hass, conf)
    _mock_hue_endpoints(hass, conf, {"1": "light.exposed"})
    hass.states.async_set("light.exposed", STATE_ON)
    await hass.async_block_till_done()
    client = await hass_client_no_auth()
    result_json = await async_get_lights(client)
    assert "1" in result_json

    hass.states.async_remove("light.exposed")
    await hass.async_block_till_done()
    result_json = await async_get_lights(client)
    assert "1" not in result_json

    hass.states.async_set("light.exposed", STATE_ON)
    await hass.async_block_till_done()
    result_json = await async_get_lights(client)

    assert "1" in result_json


async def test_get_light_state_when_none(hass_hue: HomeAssistant, hue_client) -> None:
    """Test the getting of light state when brightness is None."""
    hass_hue.states.async_set(
        "light.ceiling_lights",
        STATE_ON,
        {
            light.ATTR_BRIGHTNESS: None,
            light.ATTR_RGB_COLOR: None,
            light.ATTR_HS_COLOR: None,
            light.ATTR_COLOR_TEMP: None,
            light.ATTR_XY_COLOR: None,
            light.ATTR_SUPPORTED_COLOR_MODES: [
                light.COLOR_MODE_COLOR_TEMP,
                light.COLOR_MODE_HS,
                light.COLOR_MODE_XY,
            ],
            light.ATTR_COLOR_MODE: light.COLOR_MODE_XY,
        },
    )

    light_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTPStatus.OK
    )
    state = light_json["state"]
    assert state[HUE_API_STATE_ON] is True
    assert state[HUE_API_STATE_BRI] == 1
    assert state[HUE_API_STATE_HUE] == 0
    assert state[HUE_API_STATE_SAT] == 0
    assert state[HUE_API_STATE_CT] == 153

    hass_hue.states.async_set(
        "light.ceiling_lights",
        STATE_OFF,
        {
            light.ATTR_BRIGHTNESS: None,
            light.ATTR_RGB_COLOR: None,
            light.ATTR_HS_COLOR: None,
            light.ATTR_COLOR_TEMP: None,
            light.ATTR_XY_COLOR: None,
            light.ATTR_SUPPORTED_COLOR_MODES: [
                light.COLOR_MODE_COLOR_TEMP,
                light.COLOR_MODE_HS,
                light.COLOR_MODE_XY,
            ],
            light.ATTR_COLOR_MODE: light.COLOR_MODE_XY,
        },
    )

    light_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTPStatus.OK
    )
    state = light_json["state"]
    assert state[HUE_API_STATE_ON] is False
    assert state[HUE_API_STATE_BRI] == 1
    assert state[HUE_API_STATE_HUE] == 0
    assert state[HUE_API_STATE_SAT] == 0
    assert state[HUE_API_STATE_CT] == 153
