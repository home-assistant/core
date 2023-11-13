"""The tests for the time component."""
from datetime import time

from homeassistant.components.time import DOMAIN, SERVICE_SET_VALUE, TimeEntity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_TIME,
    CONF_PLATFORM,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


class MockTimeEntity(TimeEntity):
    """Mock time device to use in tests."""

    def __init__(self, native_value=time(12, 0, 0)) -> None:
        """Initialize mock time entity."""
        self._attr_native_value = native_value

    async def async_set_value(self, value: time) -> None:
        """Set the value of the time."""
        self._attr_native_value = value


async def test_date(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test time entity."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

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
