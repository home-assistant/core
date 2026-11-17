"""The test for the Coolmaster button platform."""

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonService
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant


async def test_button(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test the Coolmaster button."""
    assert hass.states.get("binary_sensor.l1_101_clean_filter").state == "on"

    button = hass.states.get("button.l1_101_reset_filter")
    assert button is not None
    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {
            CommonServiceArgument.ENTITY_ID: button.entity_id,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.l1_101_clean_filter").state == "off"
