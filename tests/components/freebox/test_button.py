"""Tests for the Freebox config flow."""
from unittest.mock import Mock, patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button.const import SERVICE_PRESS
from homeassistant.components.freebox.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import MOCK_HOST, MOCK_PORT

from tests.common import MockConfigEntry


async def test_reboot_button(hass: HomeAssistant, router: Mock):
    """Test reboot button."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries() == [entry]

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
