"""Device helpers for mobile_app."""
import logging
from typing import Dict

from homeassistant.components.webhook import async_register as webhook_register
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import HomeAssistantType

from .const import (ATTR_APP_ID, ATTR_CONFIG_ENTRY_ID, ATTR_DEVICE_ID,
                    ATTR_DEVICE_NAME, ATTR_MANUFACTURER, ATTR_MODEL,
                    ATTR_OS_VERSION, DATA_LOADED_REGISTRATIONS,
                    DATA_REGISTRATIONS, DATA_STORE, DOMAIN)
from .helpers import savable_state
from .webhook import handle_webhook

_LOGGER = logging.getLogger(__name__)


async def register_device(hass: HomeAssistantType, entry: ConfigEntry,
                          registration: Dict) -> dr.DeviceEntry:
    """Register a new device."""
    webhook_id = registration[CONF_WEBHOOK_ID]

    if webhook_id in hass.data[DOMAIN][DATA_LOADED_REGISTRATIONS]:
        return

    device_registry = await dr.async_get_registry(hass)

    webhook_id = registration[CONF_WEBHOOK_ID]

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={
            (ATTR_APP_ID, registration[ATTR_APP_ID]),
            (ATTR_DEVICE_ID, registration[ATTR_DEVICE_ID]),
            (CONF_WEBHOOK_ID, webhook_id)
        },
        manufacturer=registration[ATTR_MANUFACTURER],
        model=registration[ATTR_MODEL],
        name=registration[ATTR_DEVICE_NAME],
        sw_version=registration[ATTR_OS_VERSION]
    )

    registration[ATTR_CONFIG_ENTRY_ID] = entry.entry_id

    hass.data[DOMAIN][DATA_LOADED_REGISTRATIONS].append(webhook_id)
    hass.data[DOMAIN][DATA_REGISTRATIONS][webhook_id] = registration

    registration_name = 'Mobile App: {}'.format(registration[ATTR_DEVICE_NAME])
    webhook_register(hass, DOMAIN, registration_name, webhook_id,
                     handle_webhook)

    store = hass.data[DOMAIN][DATA_STORE]

    try:
        await store.async_save(savable_state(hass))
    except HomeAssistantError as ex:
        _LOGGER.error("Error saving storage! %s", ex)

    return device
