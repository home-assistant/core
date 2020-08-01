"""Services for the nfc component."""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers import device_registry as device_reg
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN as NFC_DOMAIN

ATTR_NFC_TAG_ID = "nfc_tag_id"

SERVICE_REGISTER_NFC_TAG = "register_nfc_tag"
SERVICE_NFC_TAG_SCANNED = "nfc_tag_scanned"

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMAS = {
    SERVICE_REGISTER_NFC_TAG: vol.Schema(
        {vol.Required(ATTR_NFC_TAG_ID, default=None): cv.string}
    )
}


@callback
def async_load_services(hass: HomeAssistantType):
    """Load the services exposed by the nfc component."""

    async def async_register_nfc_tag(service):
        """Create a device to store the nfc tag id in HA."""
        nfc_tag_id: str = service.data.get(ATTR_NFC_TAG_ID)
        _LOGGER.info("NFC tag registered with id: %s", nfc_tag_id)
        device_registry = await device_reg.async_get_registry(hass)
        entry = hass.data[NFC_DOMAIN]["config_entry"]
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(NFC_DOMAIN, nfc_tag_id)},
            name=nfc_tag_id,
        )

    hass.helpers.service.async_register_admin_service(
        NFC_DOMAIN,
        SERVICE_REGISTER_NFC_TAG,
        async_register_nfc_tag,
        schema=SERVICE_SCHEMAS[SERVICE_REGISTER_NFC_TAG],
    )

    async def async_nfc_tag_scanned(service):
        """Fire an event when an NFC tag is scanned."""
        nfc_tag_id: str = service.data.get(ATTR_NFC_TAG_ID)
        _LOGGER.info("NFC tag scanned with id: %s", nfc_tag_id)
        device_registry = await device_reg.async_get_registry(hass)
        device = device_registry.async_get_device({(NFC_DOMAIN, nfc_tag_id)}, {})
        hass.bus.async_fire("nfc-tag-scanned", {"nfc_tag_device_id": device.id})

    hass.helpers.service.async_register_admin_service(
        NFC_DOMAIN,
        SERVICE_NFC_TAG_SCANNED,
        async_nfc_tag_scanned,
        schema=SERVICE_SCHEMAS[SERVICE_REGISTER_NFC_TAG],
    )


@callback
def async_unload_services(hass):
    """Unload the nfc component services."""
    hass.services.async_remove(NFC_DOMAIN, SERVICE_REGISTER_NFC_TAG)
