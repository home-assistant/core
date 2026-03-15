"""Services for the HiVi Speaker integration."""

from __future__ import annotations

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
            if "device_manager" not in domain_data:
                continue
            device_manager = domain_data["device_manager"]
            ha_device_id = device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id(
                speaker_device_id
            )
            if ha_device_id is None:
                _LOGGER.warning(
                    "Cannot find HA device for speaker_device_id %s",
                    speaker_device_id,
                )
                return
            await device_manager.async_remove_device_with_entities(ha_device_id)
            await device_manager.remove_control_entities_by_speaker_device_id(
                speaker_device_id
            )
            _LOGGER.debug("Remove device %s called", speaker_device_id)
            break

    if not hass.services.has_service(DOMAIN, "refresh_discovery"):
        hass.services.async_register(
            DOMAIN, "refresh_discovery", async_handle_refresh, schema=vol.Schema({})
        )

    if not hass.services.has_service(DOMAIN, "postpone_discovery"):
        hass.services.async_register(
            DOMAIN,
            "postpone_discovery",
            async_handle_postpone_discovery,
            schema=vol.Schema({}),
        )

    if not hass.services.has_service(DOMAIN, "remove_device"):
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
