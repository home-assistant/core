"""Services for the nfc component."""
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import device_registry as device_reg
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN as NFC_DOMAIN

ATTR_NFC_TAG_ID = "nfc_tag_id"

SERVICE_REGISTER_NFC_TAG = "register_nfc_tag"
SERVICE_NFC_TAG_SCANNED = "nfc_tag_scanned"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"
ATTR_NAME = "name"
ATTR_TAG_FORMAT = "tag_format"

_LOGGER = logging.getLogger(__name__)
_UNDEF = object()

SERVICE_SCHEMAS = {
    SERVICE_REGISTER_NFC_TAG: vol.Schema(
        {
            vol.Required(ATTR_NFC_TAG_ID, default=None): cv.string,
            vol.Required(ATTR_MANUFACTURER, default=None): cv.string,
            vol.Required(ATTR_MODEL, default=None): cv.string,
            vol.Optional(ATTR_NAME, default=None): cv.string,
            vol.Optional(ATTR_TAG_FORMAT, default=None): cv.string,
        }
    )
}


@callback
def async_load_services(hass: HomeAssistantType):
    """Load the services exposed by the nfc component."""

    async def async_register_nfc_tag(service):
        """Create a device to store the nfc tag id in HA."""

        entry: ConfigEntry = hass.data[NFC_DOMAIN]["config_entry"]
        device_registry: DeviceRegistry = await device_reg.async_get_registry(hass)

        nfc_tag_id: str = service.data.get(ATTR_NFC_TAG_ID)
        manufacturer: str = service.data.get(ATTR_MANUFACTURER)
        model: str = service.data.get(ATTR_MODEL)
        custom_name: str = service.data.get(ATTR_NAME)
        tag_format: str = service.data.get(ATTR_TAG_FORMAT)

        device: DeviceEntry = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(NFC_DOMAIN, nfc_tag_id)},
            name=f"{manufacturer} - {model}".format(manufacturer, model),
            manufacturer=manufacturer,
            model=model,
            sw_version=_UNDEF if tag_format is None else tag_format,
        )

        if custom_name is not None and device.name_by_user != custom_name:
            device_registry.async_update_device(device.id, name_by_user=custom_name)

    hass.helpers.service.async_register_admin_service(
        NFC_DOMAIN,
        SERVICE_REGISTER_NFC_TAG,
        async_register_nfc_tag,
        schema=SERVICE_SCHEMAS[SERVICE_REGISTER_NFC_TAG],
    )

    async def async_nfc_tag_scanned(service):
        """Fire an event when an NFC tag is scanned."""
        device_registry: DeviceRegistry = await device_reg.async_get_registry(hass)
        nfc_tag_id: str = service.data.get(ATTR_NFC_TAG_ID)
        _LOGGER.info("NFC tag scanned with id: %s", nfc_tag_id)
        device: DeviceEntry = device_registry.async_get_device(
            {(NFC_DOMAIN, nfc_tag_id)}, {}
        )
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
