"""Test KNX number."""
from homeassistant.components.knx.const import KNX_ADDRESS
from homeassistant.components.knx.schema import NumberSchema
from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit


async def test_number_unit_of_measurement(hass: HomeAssistant, knx: KNXTestKit):
    """Test simple KNX number."""
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            NumberSchema.PLATFORM_NAME: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
                CONF_TYPE: "illuminance",
            }
        }
    )
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("number.test").attributes.get("unit_of_measurement") == "lx"
