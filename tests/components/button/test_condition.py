"""Test button conditions."""

import pytest

from homeassistant.const import CONF_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.components.common import create_target_condition


@pytest.mark.freeze_time("2026-07-01T12:00:00+00:00")
async def test_button_condition(hass: HomeAssistant) -> None:
    """Test button condition."""
    entity_id = "button.push"
    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition="button.was_pressed",
        target={CONF_ENTITY_ID: entity_id},
        behavior="any",
    )

    # Button was never pressed.
    assert condition.async_check() is False

    hass.states.async_set(entity_id, "2026-07-01T06:30:00+00:00")
    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition="button.was_pressed",
        target={CONF_ENTITY_ID: entity_id},
        behavior="any",
    )

    # Button has been pressed at some point in the past
    assert condition.async_check() is True

    condition = await create_target_condition(
        hass,
        condition="button.was_pressed",
        target={CONF_ENTITY_ID: entity_id},
        behavior="any",
        condition_options={"within": "05:00:00"},
    )

    # Button was not pressed within the last 5 hours.
    assert condition.async_check() is False

    condition = await create_target_condition(
        hass,
        condition="button.was_pressed",
        target={CONF_ENTITY_ID: entity_id},
        behavior="any",
        condition_options={"within": "06:00:00"},
    )
    # Button was pressed within the last 6 hours.
    assert condition.async_check() is True

    hass.states.async_set(entity_id, "2026-07-02T06:30:00+00:00")
    await hass.async_block_till_done()

    # Button press in the future is not valid.
    assert condition.async_check() is False


@pytest.mark.freeze_time("2026-07-01T12:00:00+00:00")
async def test_button_condition_any_all(hass: HomeAssistant) -> None:
    """Test button condition with any & all behaviors."""

    entity_ids = ["button.push1", "button.push2"]
    hass.states.async_set(entity_ids[0], STATE_UNKNOWN)
    hass.states.async_set(entity_ids[1], STATE_UNKNOWN)
    await hass.async_block_till_done()

    condition_any = await create_target_condition(
        hass,
        condition="button.was_pressed",
        target={CONF_ENTITY_ID: entity_ids},
        behavior="any",
    )
    condition_all = await create_target_condition(
        hass,
        condition="button.was_pressed",
        target={CONF_ENTITY_ID: entity_ids},
        behavior="all",
    )

    # No buttons were pressed.
    assert condition_any.async_check() is False
    assert condition_all.async_check() is False

    hass.states.async_set(entity_ids[1], "2026-07-01T06:30:00+00:00")
    await hass.async_block_till_done()

    # 1 button was pressed
    assert condition_any.async_check() is True
    assert condition_all.async_check() is False

    hass.states.async_set(entity_ids[0], "2026-07-01T06:40:00+00:00")
    await hass.async_block_till_done()

    # Both buttons were pressed
    assert condition_any.async_check() is True
    assert condition_all.async_check() is True
