"""Test datetime conditions."""

from datetime import datetime

import pytest

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.components.common import create_target_condition


@pytest.mark.freeze_time("2026-07-01T12:00:00+00:00")
async def test_datetime_condition(hass: HomeAssistant) -> None:
    """Test datetime condition."""
    entity_id = "datetime.date"
    hass.states.async_set(entity_id, "2026-07-01T13:00:00+00:00")
    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: entity_id},
        behavior="any",
    )

    # state > now
    assert condition.async_check() is False

    hass.states.async_set(entity_id, "2026-07-01T11:00:00+00:00")
    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: entity_id},
        behavior="any",
    )

    # state < now
    assert condition.async_check() is True

    condition = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: entity_id},
        behavior="any",
        condition_options={"reference": "now", "reference_offset": "-02:00:00"},
    )

    # state > (now - 2h)
    assert condition.async_check() is False


@pytest.mark.freeze_time("2026-07-01T12:00:00+00:00")
async def test_datetime_condition_any_all(hass: HomeAssistant) -> None:
    """Test datetime condition with any & all behaviors."""

    entity_ids = ["datetime.date1", "datetime.date2"]
    hass.states.async_set(entity_ids[0], "2026-07-01T20:00:00+00:00")
    hass.states.async_set(entity_ids[1], "2026-07-01T18:00:00+00:00")
    await hass.async_block_till_done()

    condition_any = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: entity_ids},
        behavior="any",
    )
    condition_all = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: entity_ids},
        behavior="all",
    )

    # Neither entity is before
    assert condition_any.async_check() is False
    assert condition_all.async_check() is False

    hass.states.async_set(entity_ids[1], "2026-07-01T06:00:00+00:00")
    await hass.async_block_till_done()

    # One entity is before
    assert condition_any.async_check() is True
    assert condition_all.async_check() is False

    hass.states.async_set(entity_ids[0], "2026-07-01T07:00:00+00:00")
    await hass.async_block_till_done()

    # Both entity is before
    assert condition_any.async_check() is True
    assert condition_all.async_check() is True


@pytest.mark.freeze_time("2026-07-01T12:00:00+00:00")
async def test_datetime_condition_entity_reference(hass: HomeAssistant) -> None:
    """Test datetime condition comparing two datetimes."""

    entity_ids = ["datetime.target", "datetime.reference"]
    hass.states.async_set(entity_ids[0], "2026-07-01T20:00:00+00:00")
    hass.states.async_set(entity_ids[1], "2026-07-01T18:00:00+00:00")
    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: entity_ids[0]},
        condition_options={"reference": entity_ids[1]},
        behavior="any",
    )

    # Target is not before reference
    assert condition.async_check() is False

    hass.states.async_set(entity_ids[1], "2026-07-01T22:00:00+00:00")
    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: entity_ids[0]},
        condition_options={"reference": entity_ids[1]},
        behavior="any",
    )

    # Target is before reference
    assert condition.async_check() is True


async def test_alternate_domains(hass: HomeAssistant) -> None:
    """Test datetime condition."""
    target_id = "sensor.datetime"
    reference_id = "input_datetime.reference"

    target_time = "2026-07-01T12:00:00+00:00"
    hass.states.async_set(
        target_id, target_time, attributes={"device_class": "timestamp"}
    )

    ts = int(datetime.fromisoformat(target_time).timestamp())
    hass.states.async_set(
        reference_id, "state dont care", attributes={"timestamp": ts + 1}
    )

    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: target_id},
        condition_options={"reference": reference_id},
        behavior="any",
    )

    # Target < Reference
    assert condition.async_check() is True

    hass.states.async_set(
        reference_id, "state dont care", attributes={"timestamp": ts - 1}
    )
    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: target_id},
        condition_options={"reference": reference_id},
        behavior="any",
    )

    # Reference < Target
    assert condition.async_check() is False
