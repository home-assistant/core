"""Services for the Netgear LTE integration."""

import voluptuous as vol

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_AUTOCONNECT,
    ATTR_FAILOVER,
    ATTR_HOST,
    ATTR_SMS_ID,
    AUTOCONNECT_MODES,
    DOMAIN,
    FAILOVER_MODES,
    LOGGER,
)
from .coordinator import NetgearLTEConfigEntry

SERVICE_DELETE_SMS = "delete_sms"
SERVICE_SET_OPTION = "set_option"
SERVICE_CONNECT_LTE = "connect_lte"
SERVICE_DISCONNECT_LTE = "disconnect_lte"

DELETE_SMS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_HOST): cv.string,
        vol.Required(ATTR_SMS_ID): vol.All(cv.ensure_list, [cv.positive_int]),
    }
)

SET_OPTION_SCHEMA = vol.Schema(
    vol.All(
        cv.has_at_least_one_key(ATTR_FAILOVER, ATTR_AUTOCONNECT),
        {
            vol.Optional(ATTR_HOST): cv.string,
            vol.Optional(ATTR_FAILOVER): vol.In(FAILOVER_MODES),
            vol.Optional(ATTR_AUTOCONNECT): vol.In(AUTOCONNECT_MODES),
        },
    )
)

CONNECT_LTE_SCHEMA = vol.Schema({vol.Optional(ATTR_HOST): cv.string})

DISCONNECT_LTE_SCHEMA = vol.Schema({vol.Optional(ATTR_HOST): cv.string})


async def _service_handler(call: ServiceCall) -> None:
    """Apply a service."""
    host = call.data.get(ATTR_HOST)

    entry: NetgearLTEConfigEntry | None = None
    for entry in call.hass.config_entries.async_loaded_entries(DOMAIN):
        if entry.data.get(CONF_HOST) == host:
            break

    if not entry or not (modem := entry.runtime_data.modem).token:
        LOGGER.error("%s: host %s unavailable", call.service, host)
        return

    if call.service == SERVICE_DELETE_SMS:
        for sms_id in call.data[ATTR_SMS_ID]:
            await modem.delete_sms(sms_id)
    elif call.service == SERVICE_SET_OPTION:
        if failover := call.data.get(ATTR_FAILOVER):
            await modem.set_failover_mode(failover)
        if autoconnect := call.data.get(ATTR_AUTOCONNECT):
            await modem.set_autoconnect_mode(autoconnect)
    elif call.service == SERVICE_CONNECT_LTE:
        await modem.connect_lte()
    elif call.service == SERVICE_DISCONNECT_LTE:
        await modem.disconnect_lte()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Netgear LTE integration."""

    service_schemas = {
        SERVICE_DELETE_SMS: DELETE_SMS_SCHEMA,
        SERVICE_SET_OPTION: SET_OPTION_SCHEMA,
        SERVICE_CONNECT_LTE: CONNECT_LTE_SCHEMA,
        SERVICE_DISCONNECT_LTE: DISCONNECT_LTE_SCHEMA,
    }

    for service, schema in service_schemas.items():
        hass.services.async_register(DOMAIN, service, _service_handler, schema=schema)
