"""The tests for the date component."""
from datetime import date

from homeassistant.components.date import DOMAIN, SERVICE_SET_VALUE, DateEntity
from homeassistant.const import (
    ATTR_DATE,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_PLATFORM,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


class MockDateEntity(DateEntity):
    """Mock date device to use in tests."""

    _attr_name = "date"

    def __init__(self, native_value=date(2020, 1, 1)) -> None:
        """Initialize mock date entity."""
        self._attr_native_value = native_value

    async def async_set_value(self, value: date) -> None:
        """Set the value of the date."""
        self._attr_native_value = value


async def test_date(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test date entity."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("date.test")
    assert state.state == "2020-01-01"
    assert state.attributes == {ATTR_FRIENDLY_NAME: "test"}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_DATE: date(2021, 1, 1), ATTR_ENTITY_ID: "date.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("date.test")
    assert state.state == "2021-01-01"

    date_entity = MockDateEntity(native_value=None)
    assert date_entity.state is None
    assert date_entity.state_attributes is None
