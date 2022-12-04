"""Test different accessory types: Air Purifiers."""

from pyhap.const import HAP_REPR_AID, HAP_REPR_CHARS, HAP_REPR_IID, HAP_REPR_VALUE

from homeassistant.components.fan import (
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN,
    FanEntityFeature,
)
from homeassistant.components.homekit.type_air_purifiers import AirPurifier
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, STATE_ON

from tests.common import async_mock_service


async def test_fan_auto_manual(hass, hk_driver, events):
    """Test switching between Auto and Manual."""
    entity_id = "fan.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED,
            ATTR_PRESET_MODE: "auto",
            ATTR_PRESET_MODES: ["auto", "smart"],
        },
    )
    await hass.async_block_till_done()
    acc = AirPurifier(hass, hk_driver, "Air Purifier", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.preset_mode_chars["auto"].value == 1
    assert acc.preset_mode_chars["smart"].value == 0

    assert acc.auto_preset is not None

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_target_air_purifier_state.value == 1

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE,
            ATTR_PRESET_MODE: "smart",
            ATTR_PRESET_MODES: ["auto", "smart"],
        },
    )
    await hass.async_block_till_done()

    assert acc.preset_mode_chars["auto"].value == 0
    assert acc.preset_mode_chars["smart"].value == 1
    assert acc.char_target_air_purifier_state.value == 0

    # Set from HomeKit
    call_set_preset_mode = async_mock_service(hass, DOMAIN, "set_preset_mode")
    call_set_percentage = async_mock_service(hass, DOMAIN, "set_percentage")

    char_auto_iid = acc.char_target_air_purifier_state.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_auto_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()

    assert acc.char_target_air_purifier_state.value == 1
    assert call_set_preset_mode[0]
    assert call_set_preset_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_preset_mode[0].data[ATTR_PRESET_MODE] == "auto"
    assert len(events) == 1
    assert events[-1].data["service"] == "set_preset_mode"

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_auto_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert acc.char_target_air_purifier_state.value == 0
    assert call_set_percentage[0]
    assert call_set_percentage[0].data[ATTR_ENTITY_ID] == entity_id
    assert events[-1].data["service"] == "set_percentage"
    assert len(events) == 2
