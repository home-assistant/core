"""deCONZ light platform tests."""
from copy import deepcopy

from homeassistant.components import deconz
import homeassistant.components.light as light
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.async_mock import patch

GROUPS = {
    "1": {
        "id": "Light group id",
        "name": "Light group",
        "type": "LightGroup",
        "state": {"all_on": False, "any_on": True},
        "action": {},
        "scenes": [],
        "lights": ["1", "2"],
    },
    "2": {
        "id": "Empty group id",
        "name": "Empty group",
        "type": "LightGroup",
        "state": {},
        "action": {},
        "scenes": [],
        "lights": [],
    },
}

LIGHTS = {
    "1": {
        "id": "RGB light id",
        "name": "RGB light",
        "state": {
            "on": True,
            "bri": 255,
            "colormode": "xy",
            "effect": "colorloop",
            "xy": (500, 500),
            "reachable": True,
        },
        "type": "Extended color light",
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    },
    "2": {
        "ctmax": 454,
        "ctmin": 155,
        "id": "Tunable white light id",
        "name": "Tunable white light",
        "state": {"on": True, "colormode": "ct", "ct": 2500, "reachable": True},
        "type": "Tunable white light",
        "uniqueid": "00:00:00:00:00:00:00:01-00",
    },
    "3": {
        "id": "On off switch id",
        "name": "On off switch",
        "type": "On/Off plug-in unit",
        "state": {"reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:02-00",
    },
    "4": {
        "name": "On off light",
        "state": {"on": True, "reachable": True},
        "type": "On and Off light",
        "uniqueid": "00:00:00:00:00:00:00:03-00",
    },
}


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert (
        await async_setup_component(
            hass, light.DOMAIN, {"light": {"platform": deconz.DOMAIN}}
        )
        is True
    )
    assert deconz.DOMAIN not in hass.data


async def test_no_lights_or_groups(hass):
    """Test that no lights or groups entities are created."""
    gateway = await setup_deconz_integration(hass)
    assert len(gateway.deconz_ids) == 0
    assert len(hass.states.async_all()) == 0


async def test_lights_and_groups(hass):
    """Test that lights or groups entities are created."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["groups"] = deepcopy(GROUPS)
    data["lights"] = deepcopy(LIGHTS)
    gateway = await setup_deconz_integration(hass, get_state_response=data)
    assert "light.rgb_light" in gateway.deconz_ids
    assert "light.tunable_white_light" in gateway.deconz_ids
    assert "light.light_group" in gateway.deconz_ids
    assert "light.empty_group" not in gateway.deconz_ids
    assert "light.on_off_switch" not in gateway.deconz_ids
    assert "light.on_off_light" in gateway.deconz_ids

    assert len(hass.states.async_all()) == 5

    rgb_light = hass.states.get("light.rgb_light")
    assert rgb_light.state == "on"
    assert rgb_light.attributes["brightness"] == 255
    assert rgb_light.attributes["hs_color"] == (224.235, 100.0)
    assert rgb_light.attributes["is_deconz_group"] is False
    assert rgb_light.attributes["supported_features"] == 61

    tunable_white_light = hass.states.get("light.tunable_white_light")
    assert tunable_white_light.state == "on"
    assert tunable_white_light.attributes["color_temp"] == 2500
    assert tunable_white_light.attributes["max_mireds"] == 454
    assert tunable_white_light.attributes["min_mireds"] == 155
    assert tunable_white_light.attributes["supported_features"] == 2

    on_off_light = hass.states.get("light.on_off_light")
    assert on_off_light.state == "on"
    assert on_off_light.attributes["supported_features"] == 0

    light_group = hass.states.get("light.light_group")
    assert light_group.state == "on"
    assert light_group.attributes["all_on"] is False

    empty_group = hass.states.get("light.empty_group")
    assert empty_group is None

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "lights",
        "id": "1",
        "state": {"on": False},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    rgb_light = hass.states.get("light.rgb_light")
    assert rgb_light.state == "off"

    rgb_light_device = gateway.api.lights["1"]

    with patch.object(rgb_light_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_ON,
            {
                "entity_id": "light.rgb_light",
                "color_temp": 2500,
                "brightness": 200,
                "transition": 5,
                "flash": "short",
                "effect": "colorloop",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put",
            "/lights/1/state",
            json={
                "ct": 2500,
                "bri": 200,
                "transitiontime": 50,
                "alert": "select",
                "effect": "colorloop",
            },
        )

    with patch.object(rgb_light_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_ON,
            {
                "entity_id": "light.rgb_light",
                "hs_color": (20, 30),
                "flash": "long",
                "effect": "None",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put",
            "/lights/1/state",
            json={"xy": (0.411, 0.351), "alert": "lselect", "effect": "none"},
        )

    with patch.object(rgb_light_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_OFF,
            {"entity_id": "light.rgb_light", "transition": 5, "flash": "short"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put",
            "/lights/1/state",
            json={"bri": 0, "transitiontime": 50, "alert": "select"},
        )

    with patch.object(rgb_light_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_OFF,
            {"entity_id": "light.rgb_light", "flash": "long"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put", "/lights/1/state", json={"alert": "lselect"}
        )

    await gateway.async_reset()

    assert len(hass.states.async_all()) == 0


async def test_disable_light_groups(hass):
    """Test successful creation of sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["groups"] = deepcopy(GROUPS)
    data["lights"] = deepcopy(LIGHTS)
    gateway = await setup_deconz_integration(
        hass,
        options={deconz.gateway.CONF_ALLOW_DECONZ_GROUPS: False},
        get_state_response=data,
    )
    assert "light.rgb_light" in gateway.deconz_ids
    assert "light.tunable_white_light" in gateway.deconz_ids
    assert "light.light_group" not in gateway.deconz_ids
    assert "light.empty_group" not in gateway.deconz_ids
    assert "light.on_off_switch" not in gateway.deconz_ids
    # 3 entities
    assert len(hass.states.async_all()) == 4

    rgb_light = hass.states.get("light.rgb_light")
    assert rgb_light is not None

    tunable_white_light = hass.states.get("light.tunable_white_light")
    assert tunable_white_light is not None

    light_group = hass.states.get("light.light_group")
    assert light_group is None

    empty_group = hass.states.get("light.empty_group")
    assert empty_group is None

    hass.config_entries.async_update_entry(
        gateway.config_entry, options={deconz.gateway.CONF_ALLOW_DECONZ_GROUPS: True}
    )
    await hass.async_block_till_done()

    assert "light.rgb_light" in gateway.deconz_ids
    assert "light.tunable_white_light" in gateway.deconz_ids
    assert "light.light_group" in gateway.deconz_ids
    assert "light.empty_group" not in gateway.deconz_ids
    assert "light.on_off_switch" not in gateway.deconz_ids
    # 3 entities
    assert len(hass.states.async_all()) == 5

    hass.config_entries.async_update_entry(
        gateway.config_entry, options={deconz.gateway.CONF_ALLOW_DECONZ_GROUPS: False}
    )
    await hass.async_block_till_done()

    assert "light.rgb_light" in gateway.deconz_ids
    assert "light.tunable_white_light" in gateway.deconz_ids
    assert "light.light_group" not in gateway.deconz_ids
    assert "light.empty_group" not in gateway.deconz_ids
    assert "light.on_off_switch" not in gateway.deconz_ids
    # 3 entities
    assert len(hass.states.async_all()) == 4
