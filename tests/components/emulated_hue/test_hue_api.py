"""The tests for the emulated Hue component."""
from datetime import timedelta
from ipaddress import ip_address
import json

from aiohttp.hdrs import CONTENT_TYPE
import pytest

from homeassistant import const, setup
from homeassistant.components import (
    climate,
    cover,
    emulated_hue,
    fan,
    http,
    light,
    media_player,
    script,
)
from homeassistant.components.emulated_hue import Config
from homeassistant.components.emulated_hue.hue_api import (
    HUE_API_STATE_BRI,
    HUE_API_STATE_HUE,
    HUE_API_STATE_ON,
    HUE_API_STATE_SAT,
    HUE_API_USERNAME,
    HueAllGroupsStateView,
    HueAllLightsStateView,
    HueConfigView,
    HueFullStateView,
    HueOneLightChangeView,
    HueOneLightStateView,
    HueUsernameView,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import (
    async_fire_time_changed,
    async_mock_service,
    get_test_instance_port,
)

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
    "11": "cover.living_room_window",
    "12": "climate.hvac",
    "13": "climate.heatpump",
    "14": "climate.ecobee",
    "15": "light.no_brightness",
}

ENTITY_NUMBERS_BY_ID = {v: k for k, v in ENTITY_IDS_BY_NUMBER.items()}


@pytest.fixture
def hass_hue(loop, hass):
    """Set up a Home Assistant instance for these tests."""
    # We need to do this to get access to homeassistant/turn_(on,off)
    loop.run_until_complete(setup.async_setup_component(hass, "homeassistant", {}))

    loop.run_until_complete(
        setup.async_setup_component(
            hass, http.DOMAIN, {http.DOMAIN: {http.CONF_SERVER_PORT: HTTP_SERVER_PORT}}
        )
    )

    with patch("homeassistant.components.emulated_hue.UPNPResponderThread"):
        loop.run_until_complete(
            setup.async_setup_component(
                hass,
                emulated_hue.DOMAIN,
                {
                    emulated_hue.DOMAIN: {
                        emulated_hue.CONF_LISTEN_PORT: BRIDGE_SERVER_PORT,
                        emulated_hue.CONF_EXPOSE_BY_DEFAULT: True,
                    }
                },
            )
        )

    loop.run_until_complete(
        setup.async_setup_component(
            hass, light.DOMAIN, {"light": [{"platform": "demo"}]}
        )
    )

    loop.run_until_complete(
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
        )
    )

    loop.run_until_complete(
        setup.async_setup_component(
            hass, climate.DOMAIN, {"climate": [{"platform": "demo"}]}
        )
    )

    loop.run_until_complete(
        setup.async_setup_component(
            hass, media_player.DOMAIN, {"media_player": [{"platform": "demo"}]}
        )
    )

    loop.run_until_complete(
        setup.async_setup_component(hass, fan.DOMAIN, {"fan": [{"platform": "demo"}]})
    )

    loop.run_until_complete(
        setup.async_setup_component(
            hass, cover.DOMAIN, {"cover": [{"platform": "demo"}]}
        )
    )

    # create a lamp without brightness support
    hass.states.async_set("light.no_brightness", "on", {})

    return hass


@pytest.fixture
def hue_client(loop, hass_hue, aiohttp_client):
    """Create web client for emulated hue api."""
    web_app = hass_hue.http.app
    config = Config(
        None,
        {
            emulated_hue.CONF_ENTITIES: {
                "light.bed_light": {emulated_hue.CONF_ENTITY_HIDDEN: True},
                # Kitchen light is explicitly excluded from being exposed
                "light.kitchen_lights": {emulated_hue.CONF_ENTITY_HIDDEN: True},
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
                # No expose setting (use default of not exposed)
                "climate.nosetting": {},
            },
        },
    )
    config.numbers = ENTITY_IDS_BY_NUMBER

    HueUsernameView().register(web_app, web_app.router)
    HueAllLightsStateView(config).register(web_app, web_app.router)
    HueOneLightStateView(config).register(web_app, web_app.router)
    HueOneLightChangeView(config).register(web_app, web_app.router)
    HueAllGroupsStateView(config).register(web_app, web_app.router)
    HueFullStateView(config).register(web_app, web_app.router)
    HueConfigView(config).register(web_app, web_app.router)

    return loop.run_until_complete(aiohttp_client(web_app))


async def test_discover_lights(hue_client):
    """Test the discovery of lights."""
    result = await hue_client.get("/api/username/lights")

    assert result.status == HTTP_OK
    assert "application/json" in result.headers["content-type"]

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


async def test_light_without_brightness_supported(hass_hue, hue_client):
    """Test that light without brightness is supported."""
    light_without_brightness_json = await perform_get_light_state(
        hue_client, "light.no_brightness", HTTP_OK
    )

    assert light_without_brightness_json["state"][HUE_API_STATE_ON] is True
    assert light_without_brightness_json["type"] == "Dimmable light"


async def test_light_without_brightness_can_be_turned_off(hass_hue, hue_client):
    """Test that light without brightness can be turned off."""
    hass_hue.states.async_set("light.no_brightness", "on", {})

    # Check if light can be turned off
    turn_off_calls = async_mock_service(hass_hue, light.DOMAIN, SERVICE_TURN_OFF)

    no_brightness_result = await perform_put_light_state(
        hass_hue, hue_client, "light.no_brightness", False
    )
    no_brightness_result_json = await no_brightness_result.json()

    assert no_brightness_result.status == HTTP_OK
    assert "application/json" in no_brightness_result.headers["content-type"]
    assert len(no_brightness_result_json) == 1

    # Verify that SERVICE_TURN_OFF has been called
    await hass_hue.async_block_till_done()
    assert len(turn_off_calls) == 1
    call = turn_off_calls[-1]

    assert light.DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert "light.no_brightness" in call.data[ATTR_ENTITY_ID]


async def test_light_without_brightness_can_be_turned_on(hass_hue, hue_client):
    """Test that light without brightness can be turned on."""
    hass_hue.states.async_set("light.no_brightness", "off", {})

    # Check if light can be turned on
    turn_on_calls = async_mock_service(hass_hue, light.DOMAIN, SERVICE_TURN_ON)

    no_brightness_result = await perform_put_light_state(
        hass_hue,
        hue_client,
        "light.no_brightness",
        True,
        # Some remotes, like HarmonyHub send brightness value regardless of light's features
        brightness=0,
    )

    no_brightness_result_json = await no_brightness_result.json()

    assert no_brightness_result.status == HTTP_OK
    assert "application/json" in no_brightness_result.headers["content-type"]
    assert len(no_brightness_result_json) == 1

    # Verify that SERVICE_TURN_ON has been called
    await hass_hue.async_block_till_done()
    assert 1 == len(turn_on_calls)
    call = turn_on_calls[-1]

    assert light.DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert "light.no_brightness" in call.data[ATTR_ENTITY_ID]


@pytest.mark.parametrize(
    "state,is_reachable",
    [
        (const.STATE_UNAVAILABLE, False),
        (const.STATE_OK, True),
        (const.STATE_UNKNOWN, True),
    ],
)
async def test_reachable_for_state(hass_hue, hue_client, state, is_reachable):
    """Test that an entity is reported as unreachable if in unavailable state."""
    entity_id = "light.ceiling_lights"

    hass_hue.states.async_set(entity_id, state)

    state_json = await perform_get_light_state(hue_client, entity_id, HTTP_OK)

    assert state_json["state"]["reachable"] == is_reachable, state_json


async def test_discover_full_state(hue_client):
    """Test the discovery of full state."""
    result = await hue_client.get(f"/api/{HUE_API_USERNAME}")

    assert result.status == HTTP_OK
    assert "application/json" in result.headers["content-type"]

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
    assert len(config_json) == 6
    assert len(lights_json) >= 1

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


async def test_discover_config(hue_client):
    """Test the discovery of configuration."""
    result = await hue_client.get(f"/api/{HUE_API_USERNAME}/config")

    assert result.status == 200
    assert "application/json" in result.headers["content-type"]

    config_json = await result.json()

    # Make sure array is correct size
    assert len(config_json) == 6

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


async def test_get_light_state(hass_hue, hue_client):
    """Test the getting of light state."""
    # Turn office light on and set to 127 brightness, and set light color
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
        hue_client, "light.ceiling_lights", HTTP_OK
    )

    assert office_json["state"][HUE_API_STATE_ON] is True
    assert office_json["state"][HUE_API_STATE_BRI] == 127
    assert office_json["state"][HUE_API_STATE_HUE] == 41869
    assert office_json["state"][HUE_API_STATE_SAT] == 217

    # Check all lights view
    result = await hue_client.get("/api/username/lights")

    assert result.status == HTTP_OK
    assert "application/json" in result.headers["content-type"]

    result_json = await result.json()

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
        hue_client, "light.ceiling_lights", HTTP_OK
    )

    assert office_json["state"][HUE_API_STATE_ON] is False
    # Removed assert HUE_API_STATE_BRI == 0 as Hue API states bri must be 1..254
    assert office_json["state"][HUE_API_STATE_HUE] == 0
    assert office_json["state"][HUE_API_STATE_SAT] == 0

    # Make sure bedroom light isn't accessible
    await perform_get_light_state(hue_client, "light.bed_light", HTTP_UNAUTHORIZED)

    # Make sure kitchen light isn't accessible
    await perform_get_light_state(hue_client, "light.kitchen_lights", HTTP_UNAUTHORIZED)


async def test_put_light_state(hass, hass_hue, hue_client):
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
        hue_client, "light.ceiling_lights", HTTP_OK
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
        hue_client, "light.ceiling_lights", HTTP_OK
    )
    assert ceiling_json["state"][HUE_API_STATE_BRI] == 254
    assert ceiling_json["state"][HUE_API_STATE_HUE] == 4369
    assert ceiling_json["state"][HUE_API_STATE_SAT] == 127

    # Go through the API to turn it off
    ceiling_result = await perform_put_light_state(
        hass_hue, hue_client, "light.ceiling_lights", False
    )

    ceiling_result_json = await ceiling_result.json()

    assert ceiling_result.status == HTTP_OK
    assert "application/json" in ceiling_result.headers["content-type"]

    assert len(ceiling_result_json) == 1

    # Check to make sure the state changed
    ceiling_lights = hass_hue.states.get("light.ceiling_lights")
    assert ceiling_lights.state == STATE_OFF
    ceiling_json = await perform_get_light_state(
        hue_client, "light.ceiling_lights", HTTP_OK
    )
    # Removed assert HUE_API_STATE_BRI == 0 as Hue API states bri must be 1..254
    assert ceiling_json["state"][HUE_API_STATE_HUE] == 0
    assert ceiling_json["state"][HUE_API_STATE_SAT] == 0

    # Make sure we can't change the bedroom light state
    bedroom_result = await perform_put_light_state(
        hass_hue, hue_client, "light.bed_light", True
    )
    assert bedroom_result.status == HTTP_UNAUTHORIZED

    # Make sure we can't change the kitchen light state
    kitchen_result = await perform_put_light_state(
        hass_hue, hue_client, "light.kitchen_lights", True
    )
    assert kitchen_result.status == HTTP_UNAUTHORIZED


async def test_put_light_state_script(hass, hass_hue, hue_client):
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

    assert script_result.status == HTTP_OK
    assert len(script_result_json) == 2

    kitchen_light = hass_hue.states.get("light.kitchen_lights")
    assert kitchen_light.state == "on"
    assert kitchen_light.attributes[light.ATTR_BRIGHTNESS] == level

    assert (
        hass.states.get("light.kitchen_lights").attributes[light.ATTR_BRIGHTNESS] == 23
    )


async def test_put_light_state_climate_set_temperature(hass_hue, hue_client):
    """Test setting climate temperature."""
    brightness = 19
    temperature = round(brightness / 254 * 100)

    hvac_result = await perform_put_light_state(
        hass_hue, hue_client, "climate.hvac", True, brightness
    )

    hvac_result_json = await hvac_result.json()

    assert hvac_result.status == HTTP_OK
    assert len(hvac_result_json) == 2

    hvac = hass_hue.states.get("climate.hvac")
    assert hvac.state == climate.const.HVAC_MODE_COOL
    assert hvac.attributes[climate.ATTR_TEMPERATURE] == temperature

    # Make sure we can't change the ecobee temperature since it's not exposed
    ecobee_result = await perform_put_light_state(
        hass_hue, hue_client, "climate.ecobee", True
    )
    assert ecobee_result.status == HTTP_UNAUTHORIZED


async def test_put_light_state_media_player(hass_hue, hue_client):
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

    assert mp_result.status == HTTP_OK
    assert len(mp_result_json) == 2

    walkman = hass_hue.states.get("media_player.walkman")
    assert walkman.state == "playing"
    assert walkman.attributes[media_player.ATTR_MEDIA_VOLUME_LEVEL] == level


async def test_close_cover(hass_hue, hue_client):
    """Test opening cover ."""
    cover_id = "cover.living_room_window"
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

    # Go through the API to turn it on
    cover_result = await perform_put_light_state(
        hass_hue, hue_client, cover_id, True, 100
    )

    assert cover_result.status == HTTP_OK
    assert "application/json" in cover_result.headers["content-type"]

    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass_hue, future)
        await hass_hue.async_block_till_done()

    cover_result_json = await cover_result.json()

    assert len(cover_result_json) == 2

    # Check to make sure the state changed
    cover_test_2 = hass_hue.states.get(cover_id)
    assert cover_test_2.state == "open"


async def test_set_position_cover(hass_hue, hue_client):
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

    level = 20
    brightness = round(level / 100 * 254)

    # Go through the API to open
    cover_result = await perform_put_light_state(
        hass_hue, hue_client, cover_id, False, brightness
    )

    assert cover_result.status == HTTP_OK
    assert "application/json" in cover_result.headers["content-type"]

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


async def test_put_light_state_fan(hass_hue, hue_client):
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

    assert fan_result.status == HTTP_OK
    assert len(fan_result_json) == 2

    living_room_fan = hass_hue.states.get("fan.living_room_fan")
    assert living_room_fan.state == "on"
    assert living_room_fan.attributes[fan.ATTR_SPEED] == fan.SPEED_MEDIUM


# pylint: disable=invalid-name
async def test_put_with_form_urlencoded_content_type(hass_hue, hue_client):
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

    assert result.status == 400


async def test_entity_not_found(hue_client):
    """Test for entity which are not found."""
    result = await hue_client.get("/api/username/lights/98")

    assert result.status == HTTP_NOT_FOUND

    result = await hue_client.put("/api/username/lights/98/state")

    assert result.status == HTTP_NOT_FOUND


async def test_allowed_methods(hue_client):
    """Test the allowed methods."""
    result = await hue_client.get(
        "/api/username/lights/ENTITY_NUMBERS_BY_ID[light.ceiling_lights]/state"
    )

    assert result.status == 405

    result = await hue_client.put(
        "/api/username/lights/ENTITY_NUMBERS_BY_ID[light.ceiling_lights]"
    )

    assert result.status == 405

    result = await hue_client.put("/api/username/lights")

    assert result.status == 405


async def test_proper_put_state_request(hue_client):
    """Test the request to set the state."""
    # Test proper on value parsing
    result = await hue_client.put(
        "/api/username/lights/{}/state".format(
            ENTITY_NUMBERS_BY_ID["light.ceiling_lights"]
        ),
        data=json.dumps({HUE_API_STATE_ON: 1234}),
    )

    assert result.status == 400

    # Test proper brightness value parsing
    result = await hue_client.put(
        "/api/username/lights/{}/state".format(
            ENTITY_NUMBERS_BY_ID["light.ceiling_lights"]
        ),
        data=json.dumps({HUE_API_STATE_ON: True, HUE_API_STATE_BRI: "Hello world!"}),
    )

    assert result.status == 400


async def test_get_empty_groups_state(hue_client):
    """Test the request to get groups endpoint."""
    # Test proper on value parsing
    result = await hue_client.get("/api/username/groups")

    assert result.status == HTTP_OK

    result_json = await result.json()

    assert result_json == {}


# pylint: disable=invalid-name
async def perform_put_test_on_ceiling_lights(
    hass_hue, hue_client, content_type="application/json"
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

    assert office_result.status == HTTP_OK
    assert "application/json" in office_result.headers["content-type"]

    office_result_json = await office_result.json()

    assert len(office_result_json) == 2

    # Check to make sure the state changed
    ceiling_lights = hass_hue.states.get("light.ceiling_lights")
    assert ceiling_lights.state == STATE_ON
    assert ceiling_lights.attributes[light.ATTR_BRIGHTNESS] == 56


async def perform_get_light_state(client, entity_id, expected_status):
    """Test the getting of a light state."""
    entity_number = ENTITY_NUMBERS_BY_ID[entity_id]
    result = await client.get(f"/api/username/lights/{entity_number}")

    assert result.status == expected_status

    if expected_status == HTTP_OK:
        assert "application/json" in result.headers["content-type"]

        return await result.json()

    return None


async def perform_put_light_state(
    hass_hue,
    client,
    entity_id,
    is_on,
    brightness=None,
    content_type="application/json",
    hue=None,
    saturation=None,
):
    """Test the setting of a light state."""
    req_headers = {"Content-Type": content_type}

    data = {HUE_API_STATE_ON: is_on}

    if brightness is not None:
        data[HUE_API_STATE_BRI] = brightness
    if hue is not None:
        data[HUE_API_STATE_HUE] = hue
    if saturation is not None:
        data[HUE_API_STATE_SAT] = saturation

    entity_number = ENTITY_NUMBERS_BY_ID[entity_id]
    result = await client.put(
        f"/api/username/lights/{entity_number}/state",
        headers=req_headers,
        data=json.dumps(data).encode(),
    )

    # Wait until state change is complete before continuing
    await hass_hue.async_block_till_done()

    return result


async def test_external_ip_blocked(hue_client):
    """Test external IP blocked."""
    getUrls = [
        "/api/username/groups",
        "/api/username",
        "/api/username/config",
        "/api/username/lights",
        "/api/username/lights/light.ceiling_lights",
    ]
    postUrls = ["/api"]
    putUrls = ["/api/username/lights/light.ceiling_lights/state"]
    with patch(
        "homeassistant.components.http.real_ip.ip_address",
        return_value=ip_address("45.45.45.45"),
    ):
        for getUrl in getUrls:
            result = await hue_client.get(getUrl)
            assert result.status == HTTP_UNAUTHORIZED

        for postUrl in postUrls:
            result = await hue_client.post(postUrl)
            assert result.status == HTTP_UNAUTHORIZED

        for putUrl in putUrls:
            result = await hue_client.put(putUrl)
            assert result.status == HTTP_UNAUTHORIZED


async def test_unauthorized_user_blocked(hue_client):
    """Test unauthorized_user blocked."""
    getUrls = [
        "/api/wronguser",
        "/api/wronguser/config",
    ]
    for getUrl in getUrls:
        result = await hue_client.get(getUrl)
        assert result.status == HTTP_OK

        result_json = await result.json()
        assert result_json[0]["error"]["description"] == "unauthorized user"
