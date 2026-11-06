"""Tests for the Wemo switch entity."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
import pywemo

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.wemo.switch import (
    ATTR_CURRENT_STATE_DETAIL,
    ATTR_ON_LATEST_TIME,
    ATTR_ON_TODAY_TIME,
    ATTR_ON_TOTAL_TIME,
    ATTR_POWER_THRESHOLD,
    ATTR_SENSOR_STATE,
    ATTR_SWITCH_MODE,
    MAKER_SWITCH_MOMENTARY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_STANDBY,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import entity_test_helpers
from .conftest import (
    MOCK_INSIGHT_STATE_THRESHOLD_POWER,
    async_create_wemo_entity,
    create_pywemo_device,
)


@pytest.fixture
def pywemo_model():
    """Pywemo LightSwitch models use the switch platform."""
    return "LightSwitch"


# Tests that are in common among wemo platforms. These test methods will be run
# in the scope of this test module. They will run using the pywemo_model from
# this test module (LightSwitch).
test_async_update_locked_multiple_updates = (
    entity_test_helpers.test_async_update_locked_multiple_updates
)
test_async_update_locked_multiple_callbacks = (
    entity_test_helpers.test_async_update_locked_multiple_callbacks
)
test_async_update_locked_callback_and_update = (
    entity_test_helpers.test_async_update_locked_callback_and_update
)


async def test_switch_registry_state_callback(
    hass: HomeAssistant, pywemo_registry, pywemo_device, wemo_entity
) -> None:
    """Verify that the switch receives state updates from the registry."""
    # On state.
    pywemo_device.get_state.return_value = 1
    pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
    await hass.async_block_till_done()
    assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

    # Off state.
    pywemo_device.get_state.return_value = 0
    pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
    await hass.async_block_till_done()
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF


async def test_switch_update_entity(
    hass: HomeAssistant, pywemo_registry, pywemo_device, wemo_entity
) -> None:
    """Verify that the switch performs state updates."""
    await async_setup_component(hass, HA_DOMAIN, {})

    # On state.
    pywemo_device.get_state.return_value = 1
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

    # Off state.
    pywemo_device.get_state.return_value = 0
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF


async def test_available_after_update(
    hass: HomeAssistant, pywemo_registry, pywemo_device, wemo_entity
) -> None:
    """Test the availability when an On call fails and after an update."""
    pywemo_device.on.side_effect = pywemo.exceptions.ActionException
    pywemo_device.get_state.return_value = 1
    await entity_test_helpers.test_avaliable_after_update(
        hass, pywemo_registry, pywemo_device, wemo_entity, SWITCH_DOMAIN
    )


async def test_turn_off_state(hass: HomeAssistant, wemo_entity) -> None:
    """Test that the device state is updated after turning off."""
    await entity_test_helpers.test_turn_off_state(hass, wemo_entity, SWITCH_DOMAIN)


async def test_insight_state_attributes(
    hass: HomeAssistant,
    pywemo_registry: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify the switch attributes are set for the Insight device.

    ``on_latest_time`` is the UTC start of the current on period. Cumulative
    today and total on-time stay duration strings.
    """
    freezer.move_to("2026-11-06T12:00:00+00:00")
    await async_setup_component(hass, HA_DOMAIN, {})
    with create_pywemo_device(pywemo_registry, "Insight") as insight:
        wemo_entity = await async_create_wemo_entity(hass, insight, "")
        assert wemo_entity is not None
        attributes = hass.states.get(wemo_entity.entity_id).attributes
        assert ATTR_ON_LATEST_TIME not in attributes
        assert attributes[ATTR_ON_TODAY_TIME] == "00d 01h 34m 38s"
        assert attributes[ATTR_ON_TOTAL_TIME] == "00d 02h 30m 12s"
        assert attributes[ATTR_POWER_THRESHOLD] == MOCK_INSIGHT_STATE_THRESHOLD_POWER
        assert attributes[ATTR_CURRENT_STATE_DETAIL] == STATE_OFF

        async def async_update() -> None:
            await hass.services.async_call(
                HA_DOMAIN,
                SERVICE_UPDATE_ENTITY,
                {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
                blocking=True,
            )

        insight.standby_state = pywemo.StandbyState.ON
        await async_update()
        attributes = hass.states.get(wemo_entity.entity_id).attributes
        assert attributes[ATTR_CURRENT_STATE_DETAIL] == STATE_ON
        on_since = dt_util.utcnow() - timedelta(seconds=insight.on_for)
        assert attributes[ATTR_ON_LATEST_TIME] == on_since
        assert attributes[ATTR_ON_TODAY_TIME] == "00d 01h 34m 38s"
        assert attributes[ATTR_ON_TOTAL_TIME] == "00d 02h 30m 12s"

        freezer.tick(timedelta(seconds=10))
        insight.on_for += 10
        await async_update()
        attributes = hass.states.get(wemo_entity.entity_id).attributes
        assert attributes[ATTR_ON_LATEST_TIME] == on_since

        insight.on_for = 5
        await async_update()
        attributes = hass.states.get(wemo_entity.entity_id).attributes
        assert attributes[ATTR_ON_LATEST_TIME] == dt_util.utcnow() - timedelta(
            seconds=5
        )

        insight.standby_state = pywemo.StandbyState.STANDBY
        await async_update()
        attributes = hass.states.get(wemo_entity.entity_id).attributes
        assert attributes[ATTR_CURRENT_STATE_DETAIL] == STATE_STANDBY
        assert attributes[ATTR_ON_LATEST_TIME] == dt_util.utcnow() - timedelta(
            seconds=5
        )

        insight.standby_state = pywemo.StandbyState.OFF
        await async_update()
        attributes = hass.states.get(wemo_entity.entity_id).attributes
        assert attributes[ATTR_CURRENT_STATE_DETAIL] == STATE_OFF
        assert ATTR_ON_LATEST_TIME not in attributes

        insight.standby_state = None
        await async_update()
        attributes = hass.states.get(wemo_entity.entity_id).attributes
        assert attributes[ATTR_CURRENT_STATE_DETAIL] == STATE_UNKNOWN
        assert ATTR_ON_LATEST_TIME not in attributes


async def test_maker_state_attributes(hass: HomeAssistant, pywemo_registry) -> None:
    """Verify the switch attributes are set for the Insight device."""
    await async_setup_component(hass, HA_DOMAIN, {})
    with create_pywemo_device(pywemo_registry, "Maker") as maker:
        wemo_entity = await async_create_wemo_entity(hass, maker, "")
        attributes = hass.states.get(wemo_entity.entity_id).attributes
        assert attributes[ATTR_SENSOR_STATE] == STATE_OFF
        assert attributes[ATTR_SWITCH_MODE] == MAKER_SWITCH_MOMENTARY

        # Test 'ON' sensor state and 'TOGGLE' switch mode values.
        maker.sensor_state = 0
        maker.switch_mode = 0
        await hass.services.async_call(
            HA_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
            blocking=True,
        )
        attributes = hass.states.get(wemo_entity.entity_id).attributes
        assert attributes[ATTR_SENSOR_STATE] == STATE_ON
