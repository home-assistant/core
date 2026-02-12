"""Tests for the require_acknowledgment feature in Google Assistant traits."""

import pytest

from homeassistant.components import light, lock, switch
from homeassistant.components.google_assistant import const, error, helpers, trait
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State

from . import BASIC_CONFIG, MockConfig

from tests.common import async_mock_service

ACK_CONFIG = MockConfig(
    entity_config={
        "light.dimmer": {const.CONF_REQUIRE_ACK: True},
        "switch.test": {const.CONF_REQUIRE_ACK: True},
        "lock.door": {const.CONF_REQUIRE_ACK: True},
    }
)

ACK_DATA = helpers.RequestData(
    ACK_CONFIG,
    "test-agent",
    const.SOURCE_CLOUD,
    "ff36a3cc-ec34-11e6-b1a0-64510650abcf",
    None,
)


async def test_brightness_require_acknowledgment(hass: HomeAssistant) -> None:
    """Test BrightnessTrait with require_acknowledgment enabled."""
    trt = trait.BrightnessTrait(
        hass,
        State("light.dimmer", light.STATE_ON, {light.ATTR_BRIGHTNESS: 243}),
        ACK_CONFIG,
    )

    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)

    # No challenge data - should raise ChallengeNeeded with ack_needed=True
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(
            trait.COMMAND_BRIGHTNESS_ABSOLUTE, ACK_DATA, {"brightness": 50}, {}
        )
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.ack_needed is True
    assert err.value.challenge_type == const.CHALLENGE_ACK_NEEDED

    # With acknowledgment data - should execute successfully
    await trt.execute(
        trait.COMMAND_BRIGHTNESS_ABSOLUTE,
        ACK_DATA,
        {"brightness": 50},
        {"ack": True},
    )
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "light.dimmer",
        light.ATTR_BRIGHTNESS_PCT: 50,
    }


async def test_onoff_require_acknowledgment(hass: HomeAssistant) -> None:
    """Test OnOffTrait with require_acknowledgment enabled."""
    trt = trait.OnOffTrait(
        hass,
        State("switch.test", "on"),
        ACK_CONFIG,
    )

    calls = async_mock_service(hass, switch.DOMAIN, "turn_off")

    # No challenge data - should raise ChallengeNeeded with ack_needed=True
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(trait.COMMAND_ON_OFF, ACK_DATA, {"on": False}, {})
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.ack_needed is True
    assert err.value.challenge_type == const.CHALLENGE_ACK_NEEDED

    # With acknowledgment data - should execute successfully
    await trt.execute(
        trait.COMMAND_ON_OFF,
        ACK_DATA,
        {"on": False},
        {"ack": True},
    )
    assert len(calls) == 1


async def test_lockunlock_require_acknowledgment(hass: HomeAssistant) -> None:
    """Test LockUnlockTrait with require_acknowledgment enabled."""
    trt = trait.LockUnlockTrait(
        hass,
        State("lock.door", lock.LockState.UNLOCKED),
        ACK_CONFIG,
    )

    calls = async_mock_service(hass, lock.DOMAIN, lock.SERVICE_LOCK)

    # No challenge data - should raise ChallengeNeeded with ack_needed=True
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(trait.COMMAND_LOCK_UNLOCK, ACK_DATA, {"lock": True}, {})
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.ack_needed is True
    assert err.value.challenge_type == const.CHALLENGE_ACK_NEEDED

    # With acknowledgment data - should execute successfully
    await trt.execute(
        trait.COMMAND_LOCK_UNLOCK,
        ACK_DATA,
        {"lock": True},
        {"ack": True},
    )
    assert len(calls) == 1


async def test_require_acknowledgment_disabled(hass: HomeAssistant) -> None:
    """Test that commands execute normally when require_acknowledgment is not set."""
    trt = trait.OnOffTrait(
        hass,
        State("switch.test", "on"),
        BASIC_CONFIG,
    )

    calls = async_mock_service(hass, switch.DOMAIN, "turn_off")

    # Without require_acknowledgment, command should execute without challenge
    basic_data = helpers.RequestData(
        BASIC_CONFIG,
        "test-agent",
        const.SOURCE_CLOUD,
        "ff36a3cc-ec34-11e6-b1a0-64510650abcf",
        None,
    )
    await trt.execute(trait.COMMAND_ON_OFF, basic_data, {"on": False}, {})

    assert len(calls) == 1
