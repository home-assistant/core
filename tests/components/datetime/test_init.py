"""The tests for the datetime component."""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest

from homeassistant.components.datetime import (
    ATTR_DATETIME,
    DOMAIN,
    SERVICE_SET_VALUE,
    DateTimeEntity,
    _async_set_value,
)
from homeassistant.const import (
    ATTR_DATE,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_TIME,
    CONF_PLATFORM,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

DEFAULT_VALUE = datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class MockDateTimeEntity(DateTimeEntity):
    """Mock datetime device to use in tests."""

    def __init__(self, native_value: datetime | None = DEFAULT_VALUE) -> None:
        """Initialize mock datetime entity."""
        self._attr_native_value = native_value

    async def async_set_value(self, value: datetime) -> None:
        """Set the value of the datetime."""
        self._attr_native_value = value


async def test_date(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test time entity."""
    hass.config.set_time_zone("utc")
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("datetime.test")
    assert state.state == "2020-01-01T01:02:03+00:00"
    assert state.attributes == {ATTR_FRIENDLY_NAME: "test"}

    # Test updating just the time
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_TIME: time(2, 3, 4), ATTR_ENTITY_ID: "datetime.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("datetime.test")
    assert state.state == "2020-01-01T02:03:04+00:00"

    # Test updating just the date
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_DATE: date(2021, 2, 2), ATTR_ENTITY_ID: "datetime.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("datetime.test")
    assert state.state == "2021-02-02T02:03:04+00:00"

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

    # Test setting partial value with None state is not allowed
    with pytest.raises(ValueError):
        await _async_set_value(
            hass,
            date_entity,
            ServiceCall(
                DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_DATE: date(2021, 12, 12)},
            ),
        )

    # Test that timezone is required to process state
    with pytest.raises(ValueError):
        assert MockDateTimeEntity(
            native_value=datetime(2020, 1, 2, 3, 4, 5, tzinfo=None)
        ).state
