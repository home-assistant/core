"""Philips Hue lights platform tests for V2 bridge/api."""

from homeassistant.components.light import COLOR_MODE_COLOR_TEMP, COLOR_MODE_XY
from homeassistant.helpers import entity_registry as er

from .conftest import setup_platform
from .const import FAKE_DEVICE, FAKE_LIGHT, FAKE_ZIGBEE_CONNECTIVITY


async def test_lights(hass, mock_bridge_v2, v2_resources_test_data):
    """Test if all v2 lights get created with correct features."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "light")
    # there shouldn't have been any requests at this point
    assert len(mock_bridge_v2.mock_requests) == 0
    # 6 entities should be created from test data (grouped_lights are disabled by default)
    assert len(hass.states.async_all()) == 6

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
    assert light_1.attributes["color_mode"] == COLOR_MODE_XY
    assert set(light_1.attributes["supported_color_modes"]) == {
        COLOR_MODE_COLOR_TEMP,
        COLOR_MODE_XY,
    }
    assert light_1.attributes["xy_color"] == (0.5614, 0.4058)
    assert light_1.attributes["min_mireds"] == 153
    assert light_1.attributes["max_mireds"] == 500
    assert light_1.attributes["dynamics"] == "dynamic_palette"

    # test light which supports color temperature only
    light_2 = hass.states.get("light.hue_light_with_color_temperature_only")
    assert light_2 is not None
    assert (
        light_2.attributes["friendly_name"] == "Hue light with color temperature only"
    )
    assert light_2.state == "off"
    assert light_2.attributes["mode"] == "normal"
    assert light_2.attributes["supported_color_modes"] == [COLOR_MODE_COLOR_TEMP]
    assert light_2.attributes["min_mireds"] == 153
    assert light_2.attributes["max_mireds"] == 454
    assert light_2.attributes["dynamics"] == "none"

    # test light which supports color only
    light_3 = hass.states.get("light.hue_light_with_color_only")
    assert light_3 is not None
    assert light_3.attributes["friendly_name"] == "Hue light with color only"
    assert light_3.state == "on"
    assert light_3.attributes["brightness"] == 128
    assert light_3.attributes["mode"] == "normal"
    assert light_3.attributes["supported_color_modes"] == [COLOR_MODE_XY]
    assert light_3.attributes["color_mode"] == COLOR_MODE_XY
    assert light_3.attributes["dynamics"] == "dynamic_palette"

    # test light which supports on/off only
    light_4 = hass.states.get("light.hue_on_off_light")
    assert light_4 is not None
    assert light_4.attributes["friendly_name"] == "Hue on/off light"
    assert light_4.state == "off"
    assert light_4.attributes["mode"] == "normal"
    assert light_4.attributes["supported_color_modes"] == []


async def test_light_turn_on_service(hass, mock_bridge_v2, v2_resources_test_data):
    """Test calling the turn on service on a light."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "light")

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
    mock_bridge_v2.mock_requests[0]["json"]["color_temperature"].pop("mirek_valid")
    mock_bridge_v2.api.emit_event("update", mock_bridge_v2.mock_requests[0]["json"])
    await hass.async_block_till_done()

    # the light should now be on
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    assert test_light.attributes["mode"] == "normal"
    assert test_light.attributes["supported_color_modes"] == [COLOR_MODE_COLOR_TEMP]
    assert test_light.attributes["color_mode"] == COLOR_MODE_COLOR_TEMP
    assert test_light.attributes["brightness"] == 255

    # test again with sending transition
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "brightness_pct": 50, "transition": 6},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 2
    assert mock_bridge_v2.mock_requests[1]["json"]["on"]["on"] is True
    assert mock_bridge_v2.mock_requests[1]["json"]["dynamics"]["duration"] == 600


async def test_light_turn_off_service(hass, mock_bridge_v2, v2_resources_test_data):
    """Test calling the turn off service on a light."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "light")

    test_light_id = "light.hue_light_with_color_and_color_temperature_1"

    # verify the light is on before we start
    assert hass.states.get(test_light_id).state == "on"

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
    mock_bridge_v2.api.emit_event("update", mock_bridge_v2.mock_requests[0]["json"])
    await hass.async_block_till_done()

    # the light should now be off
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "off"

    # test again with sending transition
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": test_light_id, "transition": 6},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 2
    assert mock_bridge_v2.mock_requests[1]["json"]["on"]["on"] is False
    assert mock_bridge_v2.mock_requests[1]["json"]["dynamics"]["duration"] == 600


async def test_light_added(hass, mock_bridge_v2):
    """Test new light added to bridge."""
    await mock_bridge_v2.api.load_test_data([FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY])

    await setup_platform(hass, mock_bridge_v2, "light")

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


async def test_light_availability(hass, mock_bridge_v2, v2_resources_test_data):
    """Test light availability property."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "light")

    test_light_id = "light.hue_light_with_color_and_color_temperature_1"

    # verify entity does exist and is available before we start
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"

    # Change availability by modififying the zigbee_connectivity status
    for status in ("connectivity_issue", "disconnected", "connected"):
        mock_bridge_v2.api.emit_event(
            "update",
            {
                "id": "1987ba66-c21d-48d0-98fb-121d939a71f3",
                "status": status,
                "type": "zigbee_connectivity",
            },
        )
        mock_bridge_v2.api.emit_event(
            "update",
            {
                "id": "02cba059-9c2c-4d45-97e4-4f79b1bfbaa1",
                "type": "light",
            },
        )
        await hass.async_block_till_done()

        # the entity should now be available only when zigbee is connected
        test_light = hass.states.get(test_light_id)
        assert test_light.state == "on" if status == "connected" else "unavailable"


async def test_grouped_lights(hass, mock_bridge_v2, v2_resources_test_data):
    """Test if all v2 grouped lights get created with correct features."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "light")

    # test if entities for hue groups are created and disabled by default
    for entity_id in ("light.test_zone", "light.test_room"):
        ent_reg = er.async_get(hass)
        entity_entry = ent_reg.async_get(entity_id)

        assert entity_entry
        assert entity_entry.disabled
        assert entity_entry.disabled_by == er.DISABLED_INTEGRATION
        # entity should not have a device assigned
        assert entity_entry.device_id is None

        # enable the entity
        updated_entry = ent_reg.async_update_entity(
            entity_entry.entity_id, **{"disabled_by": None}
        )
        assert updated_entry != entity_entry
        assert updated_entry.disabled is False

    # reload platform and check if entities are correctly there
    await hass.config_entries.async_forward_entry_unload(
        mock_bridge_v2.config_entry, "light"
    )
    await hass.config_entries.async_forward_entry_setup(
        mock_bridge_v2.config_entry, "light"
    )
    await hass.async_block_till_done()

    # test light created for hue zone
    test_entity = hass.states.get("light.test_zone")
    assert test_entity is not None
    assert test_entity.attributes["friendly_name"] == "Test Zone"
    assert test_entity.state == "on"
    assert test_entity.attributes["brightness"] == 119
    assert test_entity.attributes["color_mode"] == COLOR_MODE_XY
    assert set(test_entity.attributes["supported_color_modes"]) == {
        COLOR_MODE_COLOR_TEMP,
        COLOR_MODE_XY,
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

    # test light created for hue room
    test_entity = hass.states.get("light.test_room")
    assert test_entity is not None
    assert test_entity.attributes["friendly_name"] == "Test Room"
    assert test_entity.state == "off"
    assert test_entity.attributes["supported_color_modes"] == [COLOR_MODE_COLOR_TEMP]
    assert test_entity.attributes["min_mireds"] == 153
    assert test_entity.attributes["max_mireds"] == 454
    assert test_entity.attributes["is_hue_group"] is True
    assert test_entity.attributes["hue_scenes"] == {"Regular Test Scene"}
    assert test_entity.attributes["hue_type"] == "room"
    assert test_entity.attributes["lights"] == {
        "Hue on/off light",
        "Hue light with color temperature only",
    }

    # Test calling the turn on service on a grouped light
    test_light_id = "light.test_zone"
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": test_light_id, "brightness_pct": 100, "xy_color": (0.123, 0.123)},
        blocking=True,
    )

    # PUT request should have been sent to ALL group lights with correct params
    assert len(mock_bridge_v2.mock_requests) == 3
    for index in range(0, 3):
        assert mock_bridge_v2.mock_requests[index]["json"]["on"]["on"] is True
        assert (
            mock_bridge_v2.mock_requests[index]["json"]["dimming"]["brightness"] == 100
        )
        assert mock_bridge_v2.mock_requests[index]["json"]["color"]["xy"]["x"] == 0.123
        assert mock_bridge_v2.mock_requests[index]["json"]["color"]["xy"]["y"] == 0.123

    # Now generate update events by emitting the json we've sent as incoming events
    for index in range(0, 3):
        mock_bridge_v2.api.emit_event(
            "update", mock_bridge_v2.mock_requests[index]["json"]
        )
    await hass.async_block_till_done()

    # the light should now be on and have the properties we've set
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "on"
    assert test_light.attributes["color_mode"] == COLOR_MODE_XY
    assert test_light.attributes["brightness"] == 255
    assert test_light.attributes["xy_color"] == (0.123, 0.123)

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
    mock_bridge_v2.api.emit_event("update", mock_bridge_v2.mock_requests[0]["json"])
    await hass.async_block_till_done()

    # the light should now be off
    test_light = hass.states.get(test_light_id)
    assert test_light is not None
    assert test_light.state == "off"
