"""The tests for the datetime component."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from homeassistant.components.datetime import ATTR_DATETIME, DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import setup_test_component_platform
from tests.components.datetime.common import MockDateTimeEntity

DEFAULT_VALUE = datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)


async def test_datetime(hass: HomeAssistant) -> None:
    """Test date/time entity."""
    await hass.config.async_set_time_zone("UTC")
    setup_test_component_platform(
        hass,
        DOMAIN,
        [
            MockDateTimeEntity(
                name="test",
                unique_id="unique_datetime",
                native_value=datetime(2020, 1, 1, 1, 2, 3, tzinfo=UTC),
            )
        ],
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("datetime.test")
    assert state.state == "2020-01-01T01:02:03+00:00"
    assert state.attributes == {ATTR_FRIENDLY_NAME: "test"}

    # Test updating datetime
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_DATETIME: datetime(2022, 3, 3, 3, 4, 5), ATTR_ENTITY_ID: "datetime.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("datetime.test")
    assert state.state == "2022-03-03T03:04:05+00:00"

    # Test updating datetime with UTC timezone
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_DATETIME: "2022-03-03T03:04:05+00:00", ATTR_ENTITY_ID: "datetime.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("datetime.test")
    assert state.state == "2022-03-03T03:04:05+00:00"

    # Test updating datetime with non UTC timezone
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_DATETIME: "2022-03-03T03:04:05-05:00", ATTR_ENTITY_ID: "datetime.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("datetime.test")
    assert state.state == "2022-03-03T08:04:05+00:00"

    # Test that non UTC timezone gets converted to UTC
    assert (
        MockDateTimeEntity(
            native_value=datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("US/Eastern"))
        ).state
        == "2020-01-02T08:04:05+00:00"
    )

    # Test None state
    date_entity = MockDateTimeEntity(native_value=None)
    assert date_entity.state is None
    assert date_entity.state_attributes is None

    # Test that timezone is required to process state
    with pytest.raises(ValueError):
        assert MockDateTimeEntity(
            native_value=datetime(2020, 1, 2, 3, 4, 5, tzinfo=None)
        ).state
