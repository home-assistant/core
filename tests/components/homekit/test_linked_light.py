"""Test a light entity linked onto a fan or television accessory."""

import logging
from typing import Any
from unittest.mock import patch

from pyhap.characteristic import Characteristic
from pyhap.const import HAP_REPR_AID, HAP_REPR_CHARS, HAP_REPR_IID, HAP_REPR_VALUE
from pyhap.service import Service
import pytest
from pytest_homeassistant.common import async_mock_service

from homeassistant.components.fan import FanEntityFeature
from homeassistant.components.homekit.accessories import HomeAccessory, HomeDriver
from homeassistant.components.homekit.const import (
    CHAR_BRIGHTNESS,
    CHAR_CONFIGURED_NAME,
    CHAR_NAME,
    CHAR_ON,
    CONF_LINKED_LIGHT,
    SERV_LIGHTBULB,
)
from homeassistant.components.homekit.type_air_purifiers import AirPurifier
from homeassistant.components.homekit.type_fans import Fan
from homeassistant.components.homekit.type_media_players import (
    MediaPlayer,
    ReceiverMediaPlayer,
    TelevisionMediaPlayer,
)
from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntityCapabilityAttribute,
    LightEntityStateAttribute,
    LightServiceArgument,
)
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant

LIGHT_ID = "light.demo_light"
LIGHT_NAME = "Demo light"
FAN_ID = "fan.demo"
FAN_ATTRS = {ATTR_SUPPORTED_FEATURES: FanEntityFeature.SET_SPEED}

TV_ATTRS = {
    ATTR_DEVICE_CLASS: MediaPlayerDeviceClass.TV,
    ATTR_SUPPORTED_FEATURES: 3469,
    "source_list": ["HDMI 1", "HDMI 2"],
}

ACCESSORIES = [
    pytest.param(Fan, FAN_ID, {**FAN_ATTRS, "percentage": 50}, id="fan"),
    pytest.param(AirPurifier, "fan.demo_purifier", FAN_ATTRS, id="air_purifier"),
    pytest.param(TelevisionMediaPlayer, "media_player.demo_tv", TV_ATTRS, id="tv"),
    pytest.param(
        ReceiverMediaPlayer,
        "media_player.demo_receiver",
        {**TV_ATTRS, ATTR_DEVICE_CLASS: MediaPlayerDeviceClass.RECEIVER},
        id="receiver",
    ),
]


def _set_light(
    hass: HomeAssistant,
    state: str = STATE_ON,
    brightness: int | None = 128,
    color_modes: list[ColorMode] | None = None,
) -> None:
    """Set the state of the linked light."""
    hass.states.async_set(
        LIGHT_ID,
        state,
        {
            ATTR_FRIENDLY_NAME: LIGHT_NAME,
            LightEntityCapabilityAttribute.SUPPORTED_COLOR_MODES: color_modes
            or [ColorMode.BRIGHTNESS],
            LightEntityStateAttribute.BRIGHTNESS: brightness,
        },
    )


async def _create(
    hass: HomeAssistant,
    hk_driver: HomeDriver,
    acc_cls: type[HomeAccessory],
    entity_id: str,
    attrs: dict[str, Any],
    config: dict[str, Any] | None,
    run: bool = True,
) -> HomeAccessory:
    """Create an accessory for the main entity, and start it by default."""
    hass.states.async_set(entity_id, STATE_ON, attrs)
    await hass.async_block_till_done()
    acc = acc_cls(hass, hk_driver, "Accessory", entity_id, 1, config)
    hk_driver.add_accessory(acc)
    if run:
        acc.run()
        await hass.async_block_till_done()
    return acc


def _lightbulbs(acc: HomeAccessory) -> list[Service]:
    """Return the Lightbulb services of an accessory."""
    return [serv for serv in acc.services if serv.display_name == SERV_LIGHTBULB]


def _set_chars(
    hk_driver: HomeDriver, acc: HomeAccessory, values: dict[Characteristic, Any]
) -> None:
    """Send characteristic writes from HomeKit in one request."""
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char.to_HAP()[HAP_REPR_IID],
                    HAP_REPR_VALUE: value,
                }
                for char, value in values.items()
            ]
        },
        "mock_addr",
    )


@pytest.mark.parametrize(("acc_cls", "entity_id", "attrs"), ACCESSORIES)
async def test_linked_light_adds_lightbulb_service(
    hass: HomeAssistant,
    hk_driver: HomeDriver,
    acc_cls: type[HomeAccessory],
    entity_id: str,
    attrs: dict[str, Any],
) -> None:
    """Test a linked light adds one Lightbulb service next to the primary one."""
    _set_light(hass)
    acc = await _create(
        hass, hk_driver, acc_cls, entity_id, attrs, {CONF_LINKED_LIGHT: LIGHT_ID}
    )

    (serv_light,) = _lightbulbs(acc)
    assert serv_light.get_characteristic(CHAR_NAME).value == LIGHT_NAME
    assert serv_light.get_characteristic(CHAR_ON).value is True
    assert serv_light.get_characteristic(CHAR_BRIGHTNESS).value == 50
    assert not serv_light.is_primary_service
    primary = [serv for serv in acc.services if serv.is_primary_service]
    assert len(primary) == 1
    assert primary[0].display_name != SERV_LIGHTBULB
    assert all(serv_light not in serv.linked_services for serv in acc.services)


@pytest.mark.parametrize(("acc_cls", "entity_id", "attrs"), ACCESSORIES)
async def test_no_linked_light_no_lightbulb_service(
    hass: HomeAssistant,
    hk_driver: HomeDriver,
    acc_cls: type[HomeAccessory],
    entity_id: str,
    attrs: dict[str, Any],
) -> None:
    """Test no Lightbulb service is added without a linked light."""
    _set_light(hass)
    acc = await _create(hass, hk_driver, acc_cls, entity_id, attrs, None)

    assert _lightbulbs(acc) == []
    assert acc.linked_light is None


async def test_linked_light_ignored_by_switch_media_player(
    hass: HomeAssistant, hk_driver: HomeDriver, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a media player shown as switches ignores the linked light."""
    _set_light(hass)
    acc = await _create(
        hass,
        hk_driver,
        MediaPlayer,
        "media_player.demo_speaker",
        {ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.TURN_ON},
        {CONF_LINKED_LIGHT: LIGHT_ID, "feature_list": {"on_off": {}}},
    )

    assert _lightbulbs(acc) == []
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


async def test_linked_light_on_off_only(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test a light without brightness gets no Brightness characteristic."""
    _set_light(hass, brightness=None, color_modes=[ColorMode.ONOFF])
    acc = await _create(
        hass, hk_driver, Fan, FAN_ID, FAN_ATTRS, {CONF_LINKED_LIGHT: LIGHT_ID}
    )

    (serv_light,) = _lightbulbs(acc)
    char_types = {char.display_name for char in serv_light.characteristics}
    assert CHAR_ON in char_types
    assert CHAR_BRIGHTNESS not in char_types
    assert acc.linked_light.char_brightness is None


async def test_linked_light_unavailable_at_start(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test an unavailable light still gets brightness from its capabilities."""
    # Unavailable entities keep their capability attributes
    _set_light(hass, state=STATE_UNAVAILABLE, brightness=None)
    acc = await _create(
        hass, hk_driver, Fan, FAN_ID, FAN_ATTRS, {CONF_LINKED_LIGHT: LIGHT_ID}
    )
    assert acc.linked_light.char_brightness is not None

    _set_light(hass, brightness=255)
    await hass.async_block_till_done()
    assert acc.linked_light.char_on.value is True
    assert acc.linked_light.char_brightness.value == 100


async def test_linked_light_missing(
    hass: HomeAssistant, hk_driver: HomeDriver, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a missing linked light logs a warning and adds no service."""
    acc = await _create(
        hass, hk_driver, Fan, FAN_ID, FAN_ATTRS, {CONF_LINKED_LIGHT: LIGHT_ID}
    )

    assert _lightbulbs(acc) == []
    assert acc.linked_light is None
    assert [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
    ] == [f"{FAN_ID}: Linked light state missing: {LIGHT_ID}"]


@pytest.mark.parametrize(("acc_cls", "entity_id", "attrs"), ACCESSORIES)
async def test_linked_light_follows_state(
    hass: HomeAssistant,
    hk_driver: HomeDriver,
    acc_cls: type[HomeAccessory],
    entity_id: str,
    attrs: dict[str, Any],
) -> None:
    """Test the Lightbulb service follows the linked light."""
    _set_light(hass)
    acc = await _create(
        hass, hk_driver, acc_cls, entity_id, attrs, {CONF_LINKED_LIGHT: LIGHT_ID}
    )
    char_on = acc.linked_light.char_on
    char_brightness = acc.linked_light.char_brightness

    _set_light(hass, brightness=255)
    await hass.async_block_till_done()
    assert char_on.value is True
    assert char_brightness.value == 100

    # 0 is "off" in HomeKit, so an on light reporting 0 is shown at 1 %
    _set_light(hass, brightness=0)
    await hass.async_block_till_done()
    assert char_on.value is True
    assert char_brightness.value == 1

    _set_light(hass, state=STATE_OFF, brightness=None)
    await hass.async_block_till_done()
    assert char_on.value is False
    assert char_brightness.value == 1

    _set_light(hass, brightness=26)
    await hass.async_block_till_done()
    assert char_on.value is True
    assert char_brightness.value == 10

    for state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        _set_light(hass, state=state, brightness=None)
        await hass.async_block_till_done()
        assert char_on.value is True
        assert char_brightness.value == 10

    hass.states.async_remove(LIGHT_ID)
    await hass.async_block_till_done()
    assert char_on.value is True
    assert char_brightness.value == 10


async def test_linked_light_state_read_when_started(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test a change between creating and starting the accessory is not missed."""
    _set_light(hass, state=STATE_OFF, brightness=None)
    acc = await _create(
        hass,
        hk_driver,
        Fan,
        FAN_ID,
        FAN_ATTRS,
        {CONF_LINKED_LIGHT: LIGHT_ID},
        run=False,
    )
    assert acc.linked_light.char_on.value is False

    _set_light(hass, brightness=255)
    acc.run()
    await hass.async_block_till_done()
    assert acc.linked_light.char_on.value is True
    assert acc.linked_light.char_brightness.value == 100


async def test_linked_light_not_followed_after_stop(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test the linked light is no longer followed once the accessory stops."""
    _set_light(hass)
    acc = await _create(
        hass, hk_driver, Fan, FAN_ID, FAN_ATTRS, {CONF_LINKED_LIGHT: LIGHT_ID}
    )
    await acc.stop()

    _set_light(hass, state=STATE_OFF, brightness=None)
    await hass.async_block_till_done()
    assert acc.linked_light.char_on.value is True


@pytest.mark.parametrize(("acc_cls", "entity_id", "attrs"), ACCESSORIES)
async def test_linked_light_set_from_homekit(
    hass: HomeAssistant,
    hk_driver: HomeDriver,
    events: list[Event],
    acc_cls: type[HomeAccessory],
    entity_id: str,
    attrs: dict[str, Any],
) -> None:
    """Test HomeKit writes to the Lightbulb service call the light services."""
    _set_light(hass)
    acc = await _create(
        hass, hk_driver, acc_cls, entity_id, attrs, {CONF_LINKED_LIGHT: LIGHT_ID}
    )
    char_on = acc.linked_light.char_on
    char_brightness = acc.linked_light.char_brightness
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, LIGHT_DOMAIN, "turn_off")

    _set_chars(hk_driver, acc, {char_on: 0})
    await hass.async_block_till_done()
    assert len(call_turn_off) == 1
    assert call_turn_off[-1].data == {ATTR_ENTITY_ID: LIGHT_ID}

    _set_chars(hk_driver, acc, {char_on: 1})
    await hass.async_block_till_done()
    assert len(call_turn_on) == 1
    assert call_turn_on[-1].data == {ATTR_ENTITY_ID: LIGHT_ID}

    _set_chars(hk_driver, acc, {char_brightness: 40})
    await hass.async_block_till_done()
    assert len(call_turn_on) == 2
    assert call_turn_on[-1].data == {
        ATTR_ENTITY_ID: LIGHT_ID,
        LightServiceArgument.BRIGHTNESS_PCT: 40,
    }

    _set_chars(hk_driver, acc, {char_on: 1, char_brightness: 30})
    await hass.async_block_till_done()
    assert len(call_turn_on) == 3
    assert call_turn_on[-1].data == {
        ATTR_ENTITY_ID: LIGHT_ID,
        LightServiceArgument.BRIGHTNESS_PCT: 30,
    }

    _set_chars(hk_driver, acc, {char_brightness: 0})
    await hass.async_block_till_done()
    assert len(call_turn_off) == 2
    assert call_turn_off[-1].data == {ATTR_ENTITY_ID: LIGHT_ID}

    assert len(call_turn_on) == 3
    assert len(events) == 5
    assert all(event.data[ATTR_ENTITY_ID] == LIGHT_ID for event in events)


@pytest.mark.parametrize(
    ("on", "brightness"),
    [
        pytest.param(0, 30, id="off_with_brightness"),
        pytest.param(1, 0, id="on_with_zero_brightness"),
    ],
)
async def test_linked_light_turn_off_wins(
    hass: HomeAssistant, hk_driver: HomeDriver, on: int, brightness: int
) -> None:
    """Test a write that asks for off in any way turns the light off."""
    _set_light(hass)
    acc = await _create(
        hass, hk_driver, Fan, FAN_ID, FAN_ATTRS, {CONF_LINKED_LIGHT: LIGHT_ID}
    )
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, LIGHT_DOMAIN, "turn_off")

    _set_chars(
        hk_driver,
        acc,
        {acc.linked_light.char_on: on, acc.linked_light.char_brightness: brightness},
    )
    await hass.async_block_till_done()
    assert len(call_turn_off) == 1
    assert call_turn_on == []


async def test_linked_light_rename_does_not_turn_on(
    hass: HomeAssistant, hk_driver: HomeDriver, events: list[Event]
) -> None:
    """Test renaming the Lightbulb in the Home app calls no light service."""
    _set_light(hass, state=STATE_OFF, brightness=None)
    acc = await _create(
        hass, hk_driver, Fan, FAN_ID, FAN_ATTRS, {CONF_LINKED_LIGHT: LIGHT_ID}
    )
    call_turn_on = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, LIGHT_DOMAIN, "turn_off")
    (serv_light,) = _lightbulbs(acc)

    # The Home app writes the configured name when pairing and on rename
    _set_chars(
        hk_driver, acc, {serv_light.get_characteristic(CHAR_CONFIGURED_NAME): "Light"}
    )
    await hass.async_block_till_done()
    assert call_turn_on == []
    assert call_turn_off == []
    assert events == []


@pytest.mark.parametrize(
    ("state", "color_modes", "reloads"),
    [
        pytest.param(STATE_ON, [ColorMode.ONOFF], 1, id="modes_changed"),
        pytest.param(STATE_OFF, [ColorMode.BRIGHTNESS], 0, id="modes_unchanged"),
        pytest.param(
            STATE_UNAVAILABLE, [ColorMode.ONOFF], 0, id="modes_changed_unavailable"
        ),
    ],
)
async def test_linked_light_reload_on_color_modes_change(
    hass: HomeAssistant,
    hk_driver: HomeDriver,
    state: str,
    color_modes: list[ColorMode],
    reloads: int,
) -> None:
    """Test the accessory reloads when the linked light color modes change."""
    _set_light(hass)
    acc = await _create(
        hass, hk_driver, Fan, FAN_ID, FAN_ATTRS, {CONF_LINKED_LIGHT: LIGHT_ID}
    )

    with patch.object(acc, "async_reload") as mock_reload:
        _set_light(hass, state=state, color_modes=color_modes)
        await hass.async_block_till_done()
    assert len(mock_reload.mock_calls) == reloads
