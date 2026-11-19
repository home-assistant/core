"""Services for the Netgear LTE integration."""

from enum import StrEnum

import probatio

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import AUTOCONNECT_MODES, DOMAIN, FAILOVER_MODES
from .coordinator import NetgearLTEConfigEntry


class NetgearLTEService(StrEnum):
    """Store keys for Netgear LTE services."""

    DELETE_SMS = "delete_sms"
    SET_OPTION = "set_option"
    CONNECT_LTE = "connect_lte"
    DISCONNECT_LTE = "disconnect_lte"


class NetgearLTEServiceArgument(StrEnum):
    """Store keys for Netgear LTE service arguments."""

    HOST = "host"
    SMS_ID = "sms_id"
    FAILOVER = "failover"
    AUTOCONNECT = "autoconnect"


DELETE_SMS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(NetgearLTEServiceArgument.HOST): cv.string,
        probatio.Required(NetgearLTEServiceArgument.SMS_ID): probatio.All(
            probatio.EnsureList(), [cv.positive_int]
        ),
    }
)

SET_OPTION_SCHEMA = probatio.Schema(
    probatio.All(
        probatio.AtLeastOne(
            NetgearLTEServiceArgument.FAILOVER, NetgearLTEServiceArgument.AUTOCONNECT
        ),
        {
            probatio.Optional(NetgearLTEServiceArgument.HOST): cv.string,
            probatio.Optional(NetgearLTEServiceArgument.FAILOVER): probatio.In(
                FAILOVER_MODES
            ),
            probatio.Optional(NetgearLTEServiceArgument.AUTOCONNECT): probatio.In(
                AUTOCONNECT_MODES
            ),
        },
    )
)

CONNECT_LTE_SCHEMA = probatio.Schema(
    {probatio.Optional(NetgearLTEServiceArgument.HOST): cv.string}
)

DISCONNECT_LTE_SCHEMA = probatio.Schema(
    {probatio.Optional(NetgearLTEServiceArgument.HOST): cv.string}
)


async def _service_handler(call: ServiceCall) -> None:
    """Apply a service."""
    host = call.data.get(NetgearLTEServiceArgument.HOST)

    entry: NetgearLTEConfigEntry | None = None
    for entry in call.hass.config_entries.async_loaded_entries(DOMAIN):
        if entry.data.get(CONF_HOST) == host:
            break

    if not entry or not (modem := entry.runtime_data.modem).token:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
            translation_placeholders={"service": call.service},
        )

    if call.service == NetgearLTEService.DELETE_SMS:
        for sms_id in call.data[NetgearLTEServiceArgument.SMS_ID]:
            await modem.delete_sms(sms_id)
    elif call.service == NetgearLTEService.SET_OPTION:
        if failover := call.data.get(NetgearLTEServiceArgument.FAILOVER):
            await modem.set_failover_mode(failover)
        if autoconnect := call.data.get(NetgearLTEServiceArgument.AUTOCONNECT):
            await modem.set_autoconnect_mode(autoconnect)
    elif call.service == NetgearLTEService.CONNECT_LTE:
        await modem.connect_lte()
    elif call.service == NetgearLTEService.DISCONNECT_LTE:
        await modem.disconnect_lte()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Netgear LTE integration."""

    service_schemas = {
        NetgearLTEService.DELETE_SMS: DELETE_SMS_SCHEMA,
        NetgearLTEService.SET_OPTION: SET_OPTION_SCHEMA,
        NetgearLTEService.CONNECT_LTE: CONNECT_LTE_SCHEMA,
        NetgearLTEService.DISCONNECT_LTE: DISCONNECT_LTE_SCHEMA,
    }

    for service, schema in service_schemas.items():
        hass.services.async_register(DOMAIN, service, _service_handler, schema=schema)
