"""Tests for the require_presence feature in Google Assistant traits."""

import pytest

from homeassistant.components import light, lock, switch
from homeassistant.components.google_assistant import const, error, helpers, trait
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State

from . import BASIC_CONFIG, MockConfig

from tests.common import async_mock_service

# Configuration with global presence entity
PRESENCE_CONFIG = MockConfig(
    presence_entity="input_boolean.present",
    entity_config={
        "light.dimmer": {const.CONF_REQUIRE_PRESENCE: True},
        "switch.test": {const.CONF_REQUIRE_PRESENCE: True},
        "lock.door": {const.CONF_REQUIRE_PRESENCE: True},
    },
)

PRESENCE_DATA = helpers.RequestData(
    PRESENCE_CONFIG,
    "test-agent",
    const.SOURCE_CLOUD,
    "ff36a3cc-ec34-11e6-b1a0-64510650abcf",
    None,
)

# Configuration with per-entity presence override
PER_ENTITY_PRESENCE_CONFIG = MockConfig(
    presence_entity="input_boolean.global_presence",
    entity_config={
        "light.dimmer": {
            const.CONF_REQUIRE_PRESENCE: True,
            const.CONF_PRESENCE_ENTITY: "input_boolean.custom_presence",
        },
    },
)

PER_ENTITY_PRESENCE_DATA = helpers.RequestData(
    PER_ENTITY_PRESENCE_CONFIG,
    "test-agent",
    const.SOURCE_CLOUD,
    "ff36a3cc-ec34-11e6-b1a0-64510650abcf",
    None,
)


async def test_brightness_require_presence_home(hass: HomeAssistant) -> None:
    """Test BrightnessTrait with require_presence when user is home."""
    # Setup presence entity as ON (home)
    hass.states.async_set("input_boolean.present", STATE_ON)

    trt = trait.BrightnessTrait(
        hass,
        State("light.dimmer", light.STATE_ON, {light.ATTR_BRIGHTNESS: 243}),
        PRESENCE_CONFIG,
    )

    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)

    # With presence ON - should execute successfully
    await trt.execute(
        trait.COMMAND_BRIGHTNESS_ABSOLUTE, PRESENCE_DATA, {"brightness": 50}, {}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "light.dimmer",
        light.ATTR_BRIGHTNESS_PCT: 50,
    }


async def test_brightness_require_presence_away(hass: HomeAssistant) -> None:
    """Test BrightnessTrait with require_presence when user is away."""
    # Setup presence entity as OFF (away)
    hass.states.async_set("input_boolean.present", STATE_OFF)

    trt = trait.BrightnessTrait(
        hass,
        State("light.dimmer", light.STATE_ON, {light.ATTR_BRIGHTNESS: 243}),
        PRESENCE_CONFIG,
    )

    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)

    # With presence OFF - should raise error
    with pytest.raises(error.SmartHomeError) as err:
        await trt.execute(
            trait.COMMAND_BRIGHTNESS_ABSOLUTE, PRESENCE_DATA, {"brightness": 50}, {}
        )
    assert len(calls) == 0
    assert err.value.code == const.ERR_PRESENCE_REQUIRED
    assert "present at home" in err.value.args[0]


async def test_onoff_require_presence_away(hass: HomeAssistant) -> None:
    """Test OnOffTrait with require_presence when away."""
    hass.states.async_set("input_boolean.present", STATE_OFF)

    trt = trait.OnOffTrait(
        hass,
        State("switch.test", STATE_ON),
        PRESENCE_CONFIG,
    )

    calls = async_mock_service(hass, switch.DOMAIN, "turn_off")

    # With presence OFF - should raise error
    with pytest.raises(error.SmartHomeError) as err:
        await trt.execute(trait.COMMAND_ON_OFF, PRESENCE_DATA, {"on": False}, {})
    assert len(calls) == 0
    assert err.value.code == const.ERR_PRESENCE_REQUIRED


async def test_lockunlock_require_presence_away(hass: HomeAssistant) -> None:
    """Test LockUnlockTrait with require_presence when away."""
    hass.states.async_set("input_boolean.present", STATE_OFF)

    trt = trait.LockUnlockTrait(
        hass,
        State("lock.door", lock.LockState.UNLOCKED),
        PRESENCE_CONFIG,
    )

    calls = async_mock_service(hass, lock.DOMAIN, lock.SERVICE_LOCK)

    # With presence OFF - should raise error
    with pytest.raises(error.SmartHomeError) as err:
        await trt.execute(
            trait.COMMAND_LOCK_UNLOCK, PRESENCE_DATA, {"lock": True}, {}
        )
    assert len(calls) == 0
    assert err.value.code == const.ERR_PRESENCE_REQUIRED


async def test_require_presence_disabled(hass: HomeAssistant) -> None:
    """Test that commands execute normally when require_presence is not set."""
    # Presence is OFF but require_presence is not set
    hass.states.async_set("input_boolean.present", STATE_OFF)

    trt = trait.OnOffTrait(
        hass,
        State("switch.test", STATE_ON),
        BASIC_CONFIG,  # No require_presence
    )

    calls = async_mock_service(hass, switch.DOMAIN, "turn_off")

    basic_data = helpers.RequestData(
        BASIC_CONFIG,
        "test-agent",
        const.SOURCE_CLOUD,
        "ff36a3cc-ec34-11e6-b1a0-64510650abcf",
        None,
    )

    # Without require_presence, command should execute even when away
    await trt.execute(trait.COMMAND_ON_OFF, basic_data, {"on": False}, {})
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_per_entity_presence_override(hass: HomeAssistant) -> None:
    """Test per-entity presence_entity overrides global."""
    # Global presence is ON, custom is OFF
    hass.states.async_set("input_boolean.global_presence", STATE_ON)
    hass.states.async_set("input_boolean.custom_presence", STATE_OFF)

    trt = trait.BrightnessTrait(
        hass,
        State("light.dimmer", light.STATE_ON, {light.ATTR_BRIGHTNESS: 243}),
        PER_ENTITY_PRESENCE_CONFIG,
    )

    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)

    # Should use custom_presence (OFF), not global (ON)
    with pytest.raises(error.SmartHomeError) as err:
        await trt.execute(
            trait.COMMAND_BRIGHTNESS_ABSOLUTE,
            PER_ENTITY_PRESENCE_DATA,
            {"brightness": 50},
            {},
        )
    assert len(calls) == 0
    assert err.value.code == const.ERR_PRESENCE_REQUIRED


async def test_presence_entity_not_found_failopen(hass: HomeAssistant) -> None:
    """Test that missing presence entity fails open (allows command)."""
    # No presence entity exists
    trt = trait.OnOffTrait(
        hass,
        State("switch.test", STATE_ON),
        PRESENCE_CONFIG,
    )

    calls = async_mock_service(hass, switch.DOMAIN, "turn_off")

    # Should allow command (fail-open for safety)
    await trt.execute(trait.COMMAND_ON_OFF, PRESENCE_DATA, {"on": False}, {})
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_no_presence_entity_configured_failopen(hass: HomeAssistant) -> None:
    """Test require_presence without presence_entity configured fails open."""
    config = MockConfig(
        # No presence_entity configured
        entity_config={
            "switch.test": {const.CONF_REQUIRE_PRESENCE: True},
        },
    )

    data = helpers.RequestData(
        config,
        "test-agent",
        const.SOURCE_CLOUD,
        "ff36a3cc-ec34-11e6-b1a0-64510650abcf",
        None,
    )

    trt = trait.OnOffTrait(
        hass,
        State("switch.test", STATE_ON),
        config,
    )

    calls = async_mock_service(hass, switch.DOMAIN, "turn_off")

    # Should allow command (fail-open when not configured)
    await trt.execute(trait.COMMAND_ON_OFF, data, {"on": False}, {})
    await hass.async_block_till_done()
    assert len(calls) == 1
