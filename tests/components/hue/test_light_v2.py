"""Philips Hue lights platform tests for V2 bridge/api."""

from unittest.mock import Mock

from homeassistant.components.light import (
    ATTR_EFFECT,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform
from .const import FAKE_DEVICE, FAKE_LIGHT, FAKE_ZIGBEE_CONNECTIVITY


async def test_lights(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test if all v2 lights get created with correct features."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.LIGHT)
    # there shouldn't have been any requests at this point
    assert len(mock_bridge_v2.mock_requests) == 0
    # 8 entities should be created from test data
    assert len(hass.states.async_all()) == 8

    # test light which supports color and color temperature
    light_1 = hass.states.get("light.hue_light_with_color_and_color_temperature_1")
    assert light_1 is not None
    assert (
        light_1.attributes["friendly_name"]
        == "Hue light with color and color temperature 1"
    )
    assert light_1.state == "on"
    assert light_1.attributes["brightness"] == int(46.85 / 100 * 255)
    assert light_1.attributes["mode"] == "normal"
    assert light_1.attributes["color_mode"] == ColorMode.XY
    assert set(light_1.attributes["supported_color_modes"]) == {
        ColorMode.COLOR_TEMP,
        ColorMode.XY,
    }
    assert light_1.attributes["xy_color"] == (0.5614, 0.4058)
    assert light_1.attributes["min_mireds"] == 153
    assert light_1.attributes["max_mireds"] == 500
    assert light_1.attributes["dynamics"] == "dynamic_palette"
    assert light_1.attributes["effect_list"] == ["off", "candle", "fire"]
    assert light_1.attributes["effect"] == "off"

    # test light which supports color temperature only
    light_2 = hass.states.get("light.hue_light_with_color_temperature_only")
    assert light_2 is not None
    assert (
        light_2.attributes["friendly_name"] == "Hue light with color temperature only"
    )
    assert light_2.state == "off"
    assert light_2.attributes["mode"] == "normal"
    assert light_2.attributes["supported_color_modes"] == [ColorMode.COLOR_TEMP]
    assert light_2.attributes["min_mireds"] == 153
    assert light_2.attributes["max_mireds"] == 454
    assert light_2.attributes["dynamics"] == "none"
    assert light_2.attributes["effect_list"] == ["off", "candle", "sunrise"]

    # test light which supports color only
    light_3 = hass.states.get("light.hue_light_with_color_only")
    assert light_3 is not None
    assert light_3.attributes["friendly_name"] == "Hue light with color only"
    assert light_3.state == "on"
    assert light_3.attributes["brightness"] == 128
    assert light_3.attributes["mode"] == "normal"
    assert light_3.attributes["supported_color_modes"] == [ColorMode.XY]
    assert light_3.attributes["color_mode"] == ColorMode.XY
    assert light_3.attributes["dynamics"] == "dynamic_palette"

    # test light which supports on/off only
    light_4 = hass.states.get("light.hue_on_off_light")
    assert light_4 is not None
    assert light_4.attributes["friendly_name"] == "Hue on/off light"
    assert light_4.state == "off"
    assert light_4.attributes["mode"] == "normal"
    assert light_4.attributes["supported_color_modes"] == [ColorMode.ONOFF]


async def test_light_turn_on_service(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test calling the turn on service on a light."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.LIGHT)

    test_light_id = "light.hue_light_with_color_temperature_only"

    # verify the light is off before we start
    assert hass.states.get(test_light_id).state == "off"

    # now call the HA turn_on service
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "brightness_pct": 100, "color_temp": 300},
        blocking=True,
    )

    # PUT request should have been sent to device with correct params
    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["method"] == "put"
    assert mock_bridge_v2.mock_requests[0]["json"]["on"]["on"] is True
    assert mock_bridge_v2.mock_requests[0]["json"]["dimming"]["brightness"] == 100
    assert mock_bridge_v2.mock_requests[0]["json"]["color_temperature"]["mirek"] == 300

    # Now generate update event by emitting the json we've sent as incoming event
    event = {
        "id": "3a6710fa-4474-4eba-b533-5e6e72968feb",
        "type": "light",
        **mock_bridge_v2.mock_requests[0]["json"],
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()

    # the light should now be on
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    assert test_light.attributes["mode"] == "normal"
    assert test_light.attributes["supported_color_modes"] == [ColorMode.COLOR_TEMP]
    assert test_light.attributes["color_mode"] == ColorMode.COLOR_TEMP
    assert test_light.attributes["brightness"] == 255

    # test again with sending transition with 250ms which should round up to 200ms
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "brightness_pct": 50, "transition": 0.25},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 2
    assert mock_bridge_v2.mock_requests[1]["json"]["on"]["on"] is True
    assert mock_bridge_v2.mock_requests[1]["json"]["dynamics"]["duration"] == 200

    # test again with sending long flash
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "flash": "long"},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 3
    assert mock_bridge_v2.mock_requests[2]["json"]["alert"]["action"] == "breathe"

    # test again with sending short flash
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "flash": "short"},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 4
    assert mock_bridge_v2.mock_requests[3]["json"]["identify"]["action"] == "identify"

    # test again with sending a colortemperature which is out of range
    # which should be normalized to the upper/lower bounds Hue can handle
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "color_temp": 50},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 5
    assert mock_bridge_v2.mock_requests[4]["json"]["color_temperature"]["mirek"] == 153
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "color_temp": 550},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 6
    assert mock_bridge_v2.mock_requests[5]["json"]["color_temperature"]["mirek"] == 500

    # test enable an effect
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "effect": "candle"},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 7
    assert mock_bridge_v2.mock_requests[6]["json"]["effects"]["effect"] == "candle"
    # fire event to update effect in HA state
    event = {
        "id": "3a6710fa-4474-4eba-b533-5e6e72968feb",
        "type": "light",
        "effects": {"status": "candle"},
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.attributes["effect"] == "candle"

    # test disable effect
    # it should send a request with effect set to "no_effect"
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "effect": "off"},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 8
    assert mock_bridge_v2.mock_requests[7]["json"]["effects"]["effect"] == "no_effect"
    # fire event to update effect in HA state
    event = {
        "id": "3a6710fa-4474-4eba-b533-5e6e72968feb",
        "type": "light",
        "effects": {"status": "no_effect"},
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.attributes["effect"] == "off"

    # test turn on with useless effect
    # it should send a effect in the request if the device has no effect active
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "effect": "off"},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 9
    assert "effects" not in mock_bridge_v2.mock_requests[8]["json"]

    # test timed effect
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "effect": "sunrise", "transition": 6},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 10
    assert (
        mock_bridge_v2.mock_requests[9]["json"]["timed_effects"]["effect"] == "sunrise"
    )
    assert mock_bridge_v2.mock_requests[9]["json"]["timed_effects"]["duration"] == 6000

    # test enabling effect should ignore color temperature
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "effect": "candle", "color_temp": 500},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 11
    assert mock_bridge_v2.mock_requests[10]["json"]["effects"]["effect"] == "candle"
    assert "color_temperature" not in mock_bridge_v2.mock_requests[10]["json"]

    # test enabling effect should ignore xy color
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "effect": "candle", "xy_color": [0.123, 0.123]},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 12
    assert mock_bridge_v2.mock_requests[11]["json"]["effects"]["effect"] == "candle"
    assert "xy_color" not in mock_bridge_v2.mock_requests[11]["json"]


async def test_light_turn_off_service(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test calling the turn off service on a light."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.LIGHT)

    test_light_id = "light.hue_light_with_color_and_color_temperature_1"

    # verify the light is on before we start
    assert hass.states.get(test_light_id).state == "on"
    brightness_pct = hass.states.get(test_light_id).attributes["brightness"] / 255 * 100

    # now call the HA turn_off service
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": test_light_id},
        blocking=True,
    )

    # PUT request should have been sent to device with correct params
    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["method"] == "put"
    assert mock_bridge_v2.mock_requests[0]["json"]["on"]["on"] is False

    # Now generate update event by emitting the json we've sent as incoming event
    event = {
        "id": "02cba059-9c2c-4d45-97e4-4f79b1bfbaa1",
        "type": "light",
        **mock_bridge_v2.mock_requests[0]["json"],
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()

    # the light should now be off
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "off"

    # test again with sending transition
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": test_light_id, "transition": 0.25},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 2
    assert mock_bridge_v2.mock_requests[1]["json"]["on"]["on"] is False
    assert mock_bridge_v2.mock_requests[1]["json"]["dynamics"]["duration"] == 200

    # test turn_on resets brightness
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 3
    assert mock_bridge_v2.mock_requests[2]["json"]["on"]["on"] is True
    assert (
        round(
            mock_bridge_v2.mock_requests[2]["json"]["dimming"]["brightness"]
            - brightness_pct
        )
        == 0
    )

    # test again with sending long flash
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": test_light_id, "flash": "long"},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 4
    assert mock_bridge_v2.mock_requests[3]["json"]["alert"]["action"] == "breathe"

    # test again with sending short flash
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": test_light_id, "flash": "short"},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 5
    assert mock_bridge_v2.mock_requests[4]["json"]["identify"]["action"] == "identify"


async def test_light_added(hass: HomeAssistant, mock_bridge_v2: Mock) -> None:
    """Test new light added to bridge."""
    await mock_bridge_v2.api.load_test_data([FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY])

    await setup_platform(hass, mock_bridge_v2, Platform.LIGHT)

    test_entity_id = "light.hue_mocked_device"

    # verify entity does not exist before we start
    assert hass.states.get(test_entity_id) is None

    # Add new fake entity (and attached device and zigbee_connectivity) by emitting events
    mock_bridge_v2.api.emit_event("add", FAKE_LIGHT)
    await hass.async_block_till_done()

    # the entity should now be available
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.state == "off"
    assert test_entity.attributes["friendly_name"] == FAKE_DEVICE["metadata"]["name"]


async def test_light_availability(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test light availability property."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.LIGHT)

    test_light_id = "light.hue_light_with_color_and_color_temperature_1"

    # verify entity does exist and is available before we start
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"

    # Change availability by modifying the zigbee_connectivity status
    for status in ("connectivity_issue", "disconnected", "connected"):
        mock_bridge_v2.api.emit_event(
            "update",
            {
                "id": "1987ba66-c21d-48d0-98fb-121d939a71f3",
                "status": status,
                "type": "zigbee_connectivity",
            },
        )
        await hass.async_block_till_done()

        # the entity should now be available only when zigbee is connected
        test_light = hass.states.get(test_light_id)
        assert test_light.state == "on" if status == "connected" else "unavailable"


async def test_grouped_lights(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
) -> None:
    """Test if all v2 grouped lights get created with correct features."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.LIGHT)

    # test if entities for hue groups are created and enabled by default
    for entity_id in ("light.test_zone", "light.test_room"):
        entity_entry = entity_registry.async_get(entity_id)

        assert entity_entry
        # scene entities should have be assigned to the room/zone device/service
        assert entity_entry.device_id is not None

    # test light created for hue zone
    test_entity = hass.states.get("light.test_zone")
    assert test_entity is not None
    assert test_entity.attributes["friendly_name"] == "Test Zone"
    assert test_entity.state == "on"
    assert test_entity.attributes["brightness"] == 119
    assert test_entity.attributes["color_mode"] == ColorMode.XY
    assert set(test_entity.attributes["supported_color_modes"]) == {
        ColorMode.COLOR_TEMP,
        ColorMode.XY,
    }
    assert test_entity.attributes["min_mireds"] == 153
    assert test_entity.attributes["max_mireds"] == 500
    assert test_entity.attributes["is_hue_group"] is True
    assert test_entity.attributes["hue_scenes"] == {"Dynamic Test Scene"}
    assert test_entity.attributes["hue_type"] == "zone"
    assert test_entity.attributes["lights"] == {
        "Hue light with color and color temperature 1",
        "Hue light with color and color temperature gradient",
        "Hue light with color and color temperature 2",
    }
    assert test_entity.attributes["entity_id"] == {
        "light.hue_light_with_color_and_color_temperature_gradient",
        "light.hue_light_with_color_and_color_temperature_2",
        "light.hue_light_with_color_and_color_temperature_1",
    }

    # test light created for hue room
    test_entity = hass.states.get("light.test_room")
    assert test_entity is not None
    assert test_entity.attributes["friendly_name"] == "Test Room"
    assert test_entity.state == "off"
    assert test_entity.attributes["supported_color_modes"] == [ColorMode.COLOR_TEMP]
    assert test_entity.attributes["min_mireds"] == 153
    assert test_entity.attributes["max_mireds"] == 454
    assert test_entity.attributes["is_hue_group"] is True
    assert test_entity.attributes["hue_scenes"] == {
        "Regular Test Scene",
        "Smart Test Scene",
    }
    assert test_entity.attributes["hue_type"] == "room"
    assert test_entity.attributes["lights"] == {
        "Hue on/off light",
        "Hue light with color temperature only",
    }
    assert test_entity.attributes["entity_id"] == {
        "light.hue_light_with_color_temperature_only",
        "light.hue_on_off_light",
    }

    # Test calling the turn on service on a grouped light
    test_light_id = "light.test_zone"
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": test_light_id,
            "brightness_pct": 100,
            "xy_color": (0.123, 0.123),
            "transition": 0.25,
        },
        blocking=True,
    )

    # PUT request should have been sent to group_light with correct params
    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["json"]["on"]["on"] is True
    assert mock_bridge_v2.mock_requests[0]["json"]["dimming"]["brightness"] == 100
    assert mock_bridge_v2.mock_requests[0]["json"]["color"]["xy"]["x"] == 0.123
    assert mock_bridge_v2.mock_requests[0]["json"]["color"]["xy"]["y"] == 0.123
    assert mock_bridge_v2.mock_requests[0]["json"]["dynamics"]["duration"] == 200

    # Now generate update events by emitting the json we've sent as incoming events
    for light_id in (
        "02cba059-9c2c-4d45-97e4-4f79b1bfbaa1",
        "b3fe71ef-d0ef-48de-9355-d9e604377df0",
        "8015b17f-8336-415b-966a-b364bd082397",
    ):
        event = {
            "id": light_id,
            "type": "light",
            **mock_bridge_v2.mock_requests[0]["json"],
        }
        mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()

    # The light should now be on and have the properties we've set
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    assert test_light.attributes["color_mode"] == ColorMode.XY
    assert test_light.attributes["brightness"] == 255
    assert test_light.attributes["xy_color"] == (0.123, 0.123)

    # While we have a group on, test the color aggregation logic, XY first

    # Turn off one of the bulbs in the group
    # "hue_light_with_color_and_color_temperature_1" corresponds to "02cba059-9c2c-4d45-97e4-4f79b1bfbaa1"
    mock_bridge_v2.mock_requests.clear()
    single_light_id = "light.hue_light_with_color_and_color_temperature_1"
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": single_light_id},
        blocking=True,
    )
    event = {
        "id": "02cba059-9c2c-4d45-97e4-4f79b1bfbaa1",
        "type": "light",
        "on": {"on": False},
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()

    # The group should still show the same XY color since other lights maintain their color
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    assert test_light.attributes["xy_color"] == (0.123, 0.123)

    # Turn the light back on with a white XY color (different from the rest of the group)
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": single_light_id, "xy_color": [0.3127, 0.3290]},
        blocking=True,
    )
    event = {
        "id": "02cba059-9c2c-4d45-97e4-4f79b1bfbaa1",
        "type": "light",
        "on": {"on": True},
        "color": {"xy": {"x": 0.3127, "y": 0.3290}},
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()

    # Now the group XY color should be the average of all three lights:
    # Light 1: (0.3127, 0.3290) - white
    # Light 2: (0.123, 0.123)
    # Light 3: (0.123, 0.123)
    # Average: ((0.3127 + 0.123 + 0.123) / 3, (0.3290 + 0.123 + 0.123) / 3)
    # Average: (0.1862, 0.1917) rounded to 4 decimal places
    expected_x = round((0.3127 + 0.123 + 0.123) / 3, 4)
    expected_y = round((0.3290 + 0.123 + 0.123) / 3, 4)

    # Check that the group XY color is now the average of all lights
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    group_x, group_y = test_light.attributes["xy_color"]
    assert abs(group_x - expected_x) < 0.001  # Allow small floating point differences
    assert abs(group_y - expected_y) < 0.001

    # Test turning off another light in the group, leaving only two lights on - one white and one original color
    # "hue_light_with_color_and_color_temperature_2" corresponds to "b3fe71ef-d0ef-48de-9355-d9e604377df0"
    second_light_id = "light.hue_light_with_color_and_color_temperature_2"
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": second_light_id},
        blocking=True,
    )

    # Simulate the second light turning off
    event = {
        "id": "b3fe71ef-d0ef-48de-9355-d9e604377df0",
        "type": "light",
        "on": {"on": False},
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()

    # Now only two lights are on:
    # Light 1: (0.3127, 0.3290) - white
    # Light 3: (0.123, 0.123) - original color
    # Average of remaining lights: ((0.3127 + 0.123) / 2, (0.3290 + 0.123) / 2)
    expected_x_two_lights = round((0.3127 + 0.123) / 2, 4)
    expected_y_two_lights = round((0.3290 + 0.123) / 2, 4)

    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    # Check that the group color is now the average of only the two remaining lights
    group_x, group_y = test_light.attributes["xy_color"]
    assert abs(group_x - expected_x_two_lights) < 0.001
    assert abs(group_y - expected_y_two_lights) < 0.001

    # Test colour temperature aggregation
    # Set all three lights to colour temperature mode with different mirek values
    for mirek, light_name, light_id in zip(
        [300, 250, 200],
        [
            "light.hue_light_with_color_and_color_temperature_1",
            "light.hue_light_with_color_and_color_temperature_2",
            "light.hue_light_with_color_and_color_temperature_gradient",
        ],
        [
            "02cba059-9c2c-4d45-97e4-4f79b1bfbaa1",
            "b3fe71ef-d0ef-48de-9355-d9e604377df0",
            "8015b17f-8336-415b-966a-b364bd082397",
        ],
        strict=True,
    ):
        await hass.services.async_call(
            "light",
            "turn_on",
            {
                "entity_id": light_name,
                "color_temp": mirek,
            },
            blocking=True,
        )
        # Emit update event with matching mirek value
        mock_bridge_v2.api.emit_event(
            "update",
            {
                "id": light_id,
                "type": "light",
                "on": {"on": True},
                "color_temperature": {"mirek": mirek, "mirek_valid": True},
            },
        )
    await hass.async_block_till_done()

    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    assert test_light.attributes["color_mode"] == ColorMode.COLOR_TEMP

    # Expected average kelvin calculation:
    # 300 mirek ≈ 3333K, 250 mirek ≈ 4000K, 200 mirek ≈ 5000K
    expected_avg_kelvin = round((3333 + 4000 + 5000) / 3)
    assert abs(test_light.attributes["color_temp_kelvin"] - expected_avg_kelvin) <= 5

    # Switch light 3 off and check average kelvin temperature of remaining two lights
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.hue_light_with_color_and_color_temperature_gradient"},
        blocking=True,
    )
    event = {
        "id": "8015b17f-8336-415b-966a-b364bd082397",
        "type": "light",
        "on": {"on": False},
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()

    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    assert test_light.attributes["color_mode"] == ColorMode.COLOR_TEMP

    # Expected average kelvin calculation:
    # 300 mirek ≈ 3333K, 250 mirek ≈ 4000K
    expected_avg_kelvin = round((3333 + 4000) / 2)
    assert abs(test_light.attributes["color_temp_kelvin"] - expected_avg_kelvin) <= 5

    # Turn light 3 back on in XY mode and verify majority still favours COLOR_TEMP
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.hue_light_with_color_and_color_temperature_gradient",
            "xy_color": [0.123, 0.123],
        },
        blocking=True,
    )
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": "8015b17f-8336-415b-966a-b364bd082397",
            "type": "light",
            "on": {"on": True},
            "color": {"xy": {"x": 0.123, "y": 0.123}},
            "color_temperature": {
                "mirek": None,
                "mirek_valid": False,
            },
        },
    )
    await hass.async_block_till_done()

    test_light = hass.states.get(test_light_id)
    assert test_light.attributes["color_mode"] == ColorMode.COLOR_TEMP

    # Switch light 2 to XY mode to flip the majority
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.hue_light_with_color_and_color_temperature_2",
            "xy_color": [0.321, 0.321],
        },
        blocking=True,
    )
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": "b3fe71ef-d0ef-48de-9355-d9e604377df0",
            "type": "light",
            "on": {"on": True},
            "color": {"xy": {"x": 0.321, "y": 0.321}},
            "color_temperature": {
                "mirek": None,
                "mirek_valid": False,
            },
        },
    )
    await hass.async_block_till_done()

    test_light = hass.states.get(test_light_id)
    assert test_light.attributes["color_mode"] == ColorMode.XY

    # Test brightness aggregation with different brightness levels
    mock_bridge_v2.mock_requests.clear()

    # Set all three lights to different brightness levels
    for brightness, light_name, light_id in zip(
        [90.0, 60.0, 30.0],
        [
            "light.hue_light_with_color_and_color_temperature_1",
            "light.hue_light_with_color_and_color_temperature_2",
            "light.hue_light_with_color_and_color_temperature_gradient",
        ],
        [
            "02cba059-9c2c-4d45-97e4-4f79b1bfbaa1",
            "b3fe71ef-d0ef-48de-9355-d9e604377df0",
            "8015b17f-8336-415b-966a-b364bd082397",
        ],
        strict=True,
    ):
        await hass.services.async_call(
            "light",
            "turn_on",
            {
                "entity_id": light_name,
                "brightness": brightness,
            },
            blocking=True,
        )
        # Emit update event with matching brightness value
        mock_bridge_v2.api.emit_event(
            "update",
            {
                "id": light_id,
                "type": "light",
                "on": {"on": True},
                "dimming": {"brightness": brightness},
            },
        )
    await hass.async_block_till_done()

    # Check that the group brightness is the average of all three lights
    # Expected average: (90 + 60 + 30) / 3 = 60% -> 153 (60% of 255)
    expected_brightness = round(((90 + 60 + 30) / 3 / 100) * 255)

    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    assert test_light.attributes["brightness"] == expected_brightness

    # Turn off the dimmest light 3 (30% brightness) while keeping the other two on
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.hue_light_with_color_and_color_temperature_gradient"},
        blocking=True,
    )
    event = {
        "id": "8015b17f-8336-415b-966a-b364bd082397",
        "type": "light",
        "on": {"on": False},
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()

    # Check that the group brightness is now the average of the two remaining lights
    # Expected average: (90 + 60) / 2 = 75% -> 191 (75% of 255)
    expected_brightness_two_lights = round(((90 + 60) / 2 / 100) * 255)

    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    assert test_light.attributes["brightness"] == expected_brightness_two_lights

    # Turn off light 2 (60% brightness), leaving only the brightest one
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.hue_light_with_color_and_color_temperature_2"},
        blocking=True,
    )
    event = {
        "id": "b3fe71ef-d0ef-48de-9355-d9e604377df0",
        "type": "light",
        "on": {"on": False},
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()

    # Check that the group brightness is now just the remaining light's brightness
    # Expected brightness: 90% -> 230 (round(90 / 100 * 255))
    expected_brightness_one_light = round((90 / 100) * 255)

    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    assert test_light.attributes["brightness"] == expected_brightness_one_light

    # Set all three lights back to 100% brightness for consistency with later tests
    for light_name, light_id in zip(
        [
            "light.hue_light_with_color_and_color_temperature_1",
            "light.hue_light_with_color_and_color_temperature_2",
            "light.hue_light_with_color_and_color_temperature_gradient",
        ],
        [
            "02cba059-9c2c-4d45-97e4-4f79b1bfbaa1",
            "b3fe71ef-d0ef-48de-9355-d9e604377df0",
            "8015b17f-8336-415b-966a-b364bd082397",
        ],
        strict=True,
    ):
        await hass.services.async_call(
            "light",
            "turn_on",
            {
                "entity_id": light_name,
                "brightness": 100.0,
            },
            blocking=True,
        )
        # Emit update event with matching brightness value
        mock_bridge_v2.api.emit_event(
            "update",
            {
                "id": light_id,
                "type": "light",
                "on": {"on": True},
                "dimming": {"brightness": 100.0},
            },
        )
    await hass.async_block_till_done()

    # Verify group is back to 100% brightness
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    assert test_light.attributes["brightness"] == 255

    # Test calling the turn off service on a grouped light.
    mock_bridge_v2.mock_requests.clear()
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": test_light_id},
        blocking=True,
    )

    # PUT request should have been sent to ONLY the grouped_light resource with correct params
    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["method"] == "put"
    assert mock_bridge_v2.mock_requests[0]["json"]["on"]["on"] is False

    # Now generate update event by emitting the json we've sent as incoming event
    event = {
        "id": "f2416154-9607-43ab-a684-4453108a200e",
        "type": "grouped_light",
        **mock_bridge_v2.mock_requests[0]["json"],
    }
    mock_bridge_v2.api.emit_event("update", event)
    mock_bridge_v2.api.emit_event("update", mock_bridge_v2.mock_requests[0]["json"])
    await hass.async_block_till_done()

    # the light should now be off
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "off"

    # Test calling the turn off service on a grouped light with transition
    mock_bridge_v2.mock_requests.clear()
    test_light_id = "light.test_zone"
    await hass.services.async_call(
        "light",
        "turn_off",
        {
            "entity_id": test_light_id,
            "transition": 0.25,
        },
        blocking=True,
    )

    # PUT request should have been sent to group_light with correct params
    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["json"]["on"]["on"] is False
    assert mock_bridge_v2.mock_requests[0]["json"]["dynamics"]["duration"] == 200

    # Test turn_on resets brightness
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 2
    assert mock_bridge_v2.mock_requests[1]["json"]["on"]["on"] is True
    assert mock_bridge_v2.mock_requests[1]["json"]["dimming"]["brightness"] == 100

    # Test sending short flash effect to a grouped light
    mock_bridge_v2.mock_requests.clear()
    test_light_id = "light.test_zone"
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": test_light_id,
            "flash": "short",
        },
        blocking=True,
    )

    # PUT request should have been sent to ALL group lights with correct params
    assert len(mock_bridge_v2.mock_requests) == 3
    for index in range(3):
        assert (
            mock_bridge_v2.mock_requests[index]["json"]["identify"]["action"]
            == "identify"
        )

    # Test sending long flash effect to a grouped light
    mock_bridge_v2.mock_requests.clear()
    test_light_id = "light.test_zone"
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": test_light_id,
            "flash": "long",
        },
        blocking=True,
    )

    # PUT request should have been sent to grouped_light with correct params
    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["json"]["alert"]["action"] == "breathe"

    # Test sending flash effect in turn_off call
    mock_bridge_v2.mock_requests.clear()
    test_light_id = "light.test_zone"
    await hass.services.async_call(
        "light",
        "turn_off",
        {
            "entity_id": test_light_id,
            "flash": "short",
        },
        blocking=True,
    )

    # PUT request should have been sent to ALL group lights with correct params
    assert len(mock_bridge_v2.mock_requests) == 3
    for index in range(3):
        assert (
            mock_bridge_v2.mock_requests[index]["json"]["identify"]["action"]
            == "identify"
        )


async def test_light_turn_on_service_deprecation(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test calling the turn on service on a light."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    test_light_id = "light.hue_light_with_color_temperature_only"

    await setup_platform(hass, mock_bridge_v2, Platform.LIGHT)

    event = {
        "id": "3a6710fa-4474-4eba-b533-5e6e72968feb",
        "type": "light",
        "effects": {"status": "candle"},
    }
    mock_bridge_v2.api.emit_event("update", event)
    await hass.async_block_till_done()

    # test disable effect
    # it should send a request with effect set to "no_effect"
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: test_light_id,
            ATTR_EFFECT: "None",
        },
        blocking=True,
    )
    assert mock_bridge_v2.mock_requests[0]["json"]["effects"]["effect"] == "no_effect"
