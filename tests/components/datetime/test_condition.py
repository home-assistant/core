"""Test datetime conditions."""

import pytest

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.components.common import create_target_condition


@pytest.mark.parametrize(
    ("entity_id", "attributes"),
    [
        ("datetime.date", {}),
        ("sensor.timestamp", {"device_class": "timestamp"}),
    ],
)
@pytest.mark.freeze_time("2026-07-01T12:00:00+00:00")
async def test_datetime_condition(
    hass: HomeAssistant, entity_id: str, attributes: dict
) -> None:
    """Test datetime condition."""
    hass.states.async_set(entity_id, "2026-07-01T13:00:00+00:00", attributes=attributes)
    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: entity_id},
        behavior="any",
    )

    # state > now
    assert condition.async_check() is False

    hass.states.async_set(entity_id, "2026-07-01T11:00:00+00:00", attributes=attributes)
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


@pytest.mark.parametrize(
    ("entity", "state", "attributes"),
    [
        (
            "sensor.timestamp",
            "invalid",
            {"device_class": "timestamp"},
        ),
        ("datetime.invalid", "invalid", {}),
    ],
)
@pytest.mark.freeze_time("2026-07-01T12:00:00+00:00")
async def test_invalid(hass: HomeAssistant, entity, state, attributes) -> None:
    """Test datetime handling with invalid entities."""

    hass.states.async_set(entity, state, attributes=attributes)
    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: entity},
        behavior="any",
    )

    assert condition.async_check() is False

    condition = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: entity},
        behavior="all",
    )

    assert condition.async_check() is False


@pytest.mark.freeze_time("2026-07-01T12:00:00+00:00")
async def test_invalid_2(hass: HomeAssistant) -> None:
    """Test datetime handling with invalid reference entity."""

    target_id = "datetime.target"
    hass.states.async_set(target_id, "2026-07-01T20:00:00+00:00")
    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition="datetime.is_before",
        target={CONF_ENTITY_ID: target_id},
        condition_options={"reference": "datetime.i_dont_exist"},
        behavior="any",
    )

    assert condition.async_check() is False
