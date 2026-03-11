import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register HiVi Speaker services."""

    async def async_handle_refresh(call) -> None:
        """Handle refresh_discovery service call."""
        if DOMAIN not in hass.data:
            _LOGGER.warning("%s not initialized", DOMAIN)
            return

        for domain_data in hass.data[DOMAIN].values():
            if "device_manager" in domain_data:
                await domain_data["device_manager"].refresh_discovery()
                _LOGGER.debug("Refresh discovery called")
                break

    async def async_handle_postpone_discovery(call) -> None:
        """Handle postpone_discovery service call."""
        if DOMAIN not in hass.data:
            _LOGGER.warning("%s not initialized", DOMAIN)
            return

        for domain_data in hass.data[DOMAIN].values():
            if "device_manager" in domain_data:
                await domain_data["device_manager"].postpone_discovery()
                _LOGGER.debug("Postpone discovery called")
                break

    async def async_handle_remove_device(call) -> None:
        """Handle remove_device service call."""
        speaker_device_id = call.data["speaker_device_id"]

        if DOMAIN not in hass.data:
            _LOGGER.warning("%s not initialized", DOMAIN)
            return

        for domain_data in hass.data[DOMAIN].values():
            if "device_manager" in domain_data:
                success = await domain_data["device_manager"].remove_device(
                    speaker_device_id
                )
                if success:
                    _LOGGER.debug("Remove device %s called", speaker_device_id)
                    break

    hass.services.async_register(
        DOMAIN, "refresh_discovery", async_handle_refresh, schema=vol.Schema({})
    )

    hass.services.async_register(
        DOMAIN,
        "postpone_discovery",
        async_handle_postpone_discovery,
        schema=vol.Schema({}),
    )

    hass.services.async_register(
        DOMAIN,
        "remove_device",
        async_handle_remove_device,
        schema=vol.Schema(
            {
                vol.Required("speaker_device_id"): str,
            }
        ),
    )
