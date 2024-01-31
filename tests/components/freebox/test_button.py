"""Tests for the Freebox buttons."""
from unittest.mock import ANY, AsyncMock, Mock, patch

from pytest_unordered import unordered

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_reboot(hass: HomeAssistant, router: Mock) -> None:
    """Test reboot button."""
    entry = await setup_platform(hass, BUTTON_DOMAIN)

    assert hass.config_entries.async_entries() == unordered([entry, ANY])

    assert router.call_count == 1
    assert router().open.call_count == 1

    with patch(
        "homeassistant.components.freebox.router.FreeboxRouter.reboot"
    ) as mock_service:
        mock_service.assert_not_called()
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


async def test_mark_calls_as_read(hass: HomeAssistant, router: Mock) -> None:
    """Test mark calls as read button."""
    entry = await setup_platform(hass, BUTTON_DOMAIN)

    assert hass.config_entries.async_entries() == unordered([entry, ANY])

    assert router.call_count == 1
    assert router().open.call_count == 1

    with patch(
        "homeassistant.components.freebox.router.FreeboxRouter.call"
    ) as mock_service:
        mock_service.mark_calls_log_as_read = AsyncMock()
        mock_service.mark_calls_log_as_read.assert_not_called()
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            service_data={
                ATTR_ENTITY_ID: "button.mark_calls_as_read",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_service.mark_calls_log_as_read.assert_called_once()
