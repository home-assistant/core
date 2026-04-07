"""Tests for the Homecast light platform."""

from unittest.mock import AsyncMock

from pyhomecast import HomecastDevice, HomecastHome, HomecastState

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

COLOR_TEMP_STATE = HomecastState(
    devices={
        "my_home_0bf8.living_room_a1b2.desk_lamp_aa11": HomecastDevice(
            unique_id="my_home_0bf8.living_room_a1b2.desk_lamp_aa11",
            name="Desk Lamp",
            room_name="Living Room",
            home_key="my_home_0bf8",
            home_name="My Home",
            room_key="living_room_a1b2",
            accessory_key="desk_lamp_aa11",
            device_type="light",
            state={"on": True, "brightness": 60, "color_temp": 250},
            settable=["on", "brightness", "color_temp"],
        ),
    },
    homes={"my_home_0bf8": HomecastHome(key="my_home_0bf8", name="My Home")},
)

BRIGHTNESS_ONLY_STATE = HomecastState(
    devices={
        "my_home_0bf8.living_room_a1b2.dimmer_bb22": HomecastDevice(
            unique_id="my_home_0bf8.living_room_a1b2.dimmer_bb22",
            name="Dimmer",
            room_name="Living Room",
            home_key="my_home_0bf8",
            home_name="My Home",
            room_key="living_room_a1b2",
            accessory_key="dimmer_bb22",
            device_type="light",
            state={"on": False, "brightness": 0},
            settable=["on", "brightness"],
        ),
    },
    homes={"my_home_0bf8": HomecastHome(key="my_home_0bf8", name="My Home")},
)

ONOFF_ONLY_STATE = HomecastState(
    devices={
        "my_home_0bf8.living_room_a1b2.bulb_cc33": HomecastDevice(
            unique_id="my_home_0bf8.living_room_a1b2.bulb_cc33",
            name="Bulb",
            room_name="Living Room",
            home_key="my_home_0bf8",
            home_name="My Home",
            room_key="living_room_a1b2",
            accessory_key="bulb_cc33",
            device_type="light",
            state={"on": True},
            settable=["on"],
        ),
    },
    homes={"my_home_0bf8": HomecastHome(key="my_home_0bf8", name="My Home")},
)

MULTI_HOME_STATE = HomecastState(
    devices={
        "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4": HomecastDevice(
            unique_id="my_home_0bf8.living_room_a1b2.ceiling_light_c3d4",
            name="Ceiling Light",
            room_name="Living Room",
            home_key="my_home_0bf8",
            home_name="My Home",
            room_key="living_room_a1b2",
            accessory_key="ceiling_light_c3d4",
            device_type="light",
            state={"on": True, "brightness": 80, "hue": 45, "saturation": 100},
            settable=["on", "brightness", "hue", "saturation"],
        ),
        "beach_house_1234.patio_5678.string_lights_abcd": HomecastDevice(
            unique_id="beach_house_1234.patio_5678.string_lights_abcd",
            name="String Lights",
            room_name="Patio",
            home_key="beach_house_1234",
            home_name="Beach House",
            room_key="patio_5678",
            accessory_key="string_lights_abcd",
            device_type="light",
            state={"on": False},
            settable=["on"],
        ),
    },
    homes={
        "my_home_0bf8": HomecastHome(key="my_home_0bf8", name="My Home"),
        "beach_house_1234": HomecastHome(key="beach_house_1234", name="Beach House"),
    },
)


async def test_light_setup(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that light entities are created for light devices."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.ceiling_light")
    assert state is not None
    assert state.state == "on"


async def test_light_brightness(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light brightness is converted from 0-100 to 0-255."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.ceiling_light")
    assert state is not None
    # 80% -> 204/255
    assert state.attributes.get(ATTR_BRIGHTNESS) == round(80 * 255 / 100)


async def test_light_hs_color(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light HS color."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.ceiling_light")
    assert state is not None
    assert state.attributes.get(ATTR_HS_COLOR) == (45.0, 100.0)


async def test_light_color_mode(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light reports HS color mode when hue+saturation are settable."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.ceiling_light")
    assert state is not None
    assert state.attributes.get("color_mode") == ColorMode.HS


async def test_light_turn_on(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on a light."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.ceiling_light", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    mock_homecast.set_state.assert_called_once()
    call_args = mock_homecast.set_state.call_args[0][0]
    props = call_args["my_home_0bf8"]["living_room_a1b2"]["ceiling_light_c3d4"]
    assert props["on"] is True
    assert props["brightness"] == round(128 / 255 * 100)


async def test_light_turn_on_with_hs_color(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on a light with HS color."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.ceiling_light", ATTR_HS_COLOR: (120.0, 50.0)},
        blocking=True,
    )

    mock_homecast.set_state.assert_called_once()
    call_args = mock_homecast.set_state.call_args[0][0]
    props = call_args["my_home_0bf8"]["living_room_a1b2"]["ceiling_light_c3d4"]
    assert props["on"] is True
    assert props["hue"] == 120
    assert props["saturation"] == 50


async def test_light_turn_off(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off a light."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.ceiling_light"},
        blocking=True,
    )

    mock_homecast.set_state.assert_called_once()
    call_args = mock_homecast.set_state.call_args[0][0]
    props = call_args["my_home_0bf8"]["living_room_a1b2"]["ceiling_light_c3d4"]
    assert props["on"] is False


async def test_light_color_temp_mode(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light with color_temp settable reports COLOR_TEMP mode."""
    mock_homecast.get_state = AsyncMock(return_value=COLOR_TEMP_STATE)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.desk_lamp")
    assert state is not None
    assert state.attributes.get("color_mode") == ColorMode.COLOR_TEMP
    assert state.attributes.get("supported_color_modes") == [ColorMode.COLOR_TEMP]
    # 250 mirek -> 4000K
    assert state.attributes.get("color_temp_kelvin") == 4000
    assert state.attributes.get("min_color_temp_kelvin") == 2000
    assert state.attributes.get("max_color_temp_kelvin") == 7143


async def test_light_turn_on_with_color_temp(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on a light with color temperature."""
    mock_homecast.get_state = AsyncMock(return_value=COLOR_TEMP_STATE)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.desk_lamp", ATTR_COLOR_TEMP_KELVIN: 3000},
        blocking=True,
    )

    mock_homecast.set_state.assert_called_once()
    call_args = mock_homecast.set_state.call_args[0][0]
    props = call_args["my_home_0bf8"]["living_room_a1b2"]["desk_lamp_aa11"]
    assert props["on"] is True
    assert props["color_temp"] == round(1_000_000 / 3000)


async def test_light_brightness_only_mode(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light with only brightness settable reports BRIGHTNESS mode."""
    mock_homecast.get_state = AsyncMock(return_value=BRIGHTNESS_ONLY_STATE)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.dimmer")
    assert state is not None
    assert state.attributes.get("supported_color_modes") == [ColorMode.BRIGHTNESS]


async def test_light_onoff_only_mode(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light with only on/off settable reports ONOFF mode."""
    mock_homecast.get_state = AsyncMock(return_value=ONOFF_ONLY_STATE)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.bulb")
    assert state is not None
    assert state.attributes.get("color_mode") == ColorMode.ONOFF
    assert state.attributes.get("supported_color_modes") == [ColorMode.ONOFF]


async def test_light_multi_home_area_naming(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that multi-home setups prefix room name with home name."""
    mock_homecast.get_state = AsyncMock(return_value=MULTI_HOME_STATE)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Both homes' lights should exist
    state1 = hass.states.get("light.ceiling_light")
    state2 = hass.states.get("light.string_lights")
    assert state1 is not None
    assert state2 is not None
