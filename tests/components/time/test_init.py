"""The tests for the time component."""

from datetime import time

from homeassistant.components.time import DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_TIME,
    CONF_PLATFORM,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import MockTimeEntity

from tests.common import setup_test_component_platform


async def test_date(hass: HomeAssistant) -> None:
    """Test time entity."""
    entity = MockTimeEntity(
        name="test",
        unique_id="unique_time",
        native_value=time(1, 2, 3),
    )
    setup_test_component_platform(hass, DOMAIN, [entity])

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("time.test")
    assert state.state == "01:02:03"
    assert state.attributes == {ATTR_FRIENDLY_NAME: "test"}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_TIME: time(2, 3, 4), ATTR_ENTITY_ID: "time.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("time.test")
    assert state.state == "02:03:04"

    date_entity = MockTimeEntity(native_value=None)
    assert date_entity.state is None
    assert date_entity.state_attributes is None
