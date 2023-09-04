"""Tests for the Freebox config flow."""
from unittest.mock import ANY, Mock, patch

from pytest_unordered import unordered

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_reboot_button(hass: HomeAssistant, router: Mock) -> None:
    """Test reboot button."""
    entry = await setup_platform(hass, BUTTON_DOMAIN)

    assert hass.config_entries.async_entries() == unordered([entry, ANY])

    assert router.call_count == 1
    assert router().open.call_count == 1

    with patch(
        "homeassistant.components.freebox.router.FreeboxRouter.reboot"
    ) as mock_service:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            service_data={
                ATTR_ENTITY_ID: "button.reboot_freebox",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_service.assert_called_once()
