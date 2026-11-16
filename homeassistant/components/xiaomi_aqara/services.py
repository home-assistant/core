"""Services for the Xiaomi Aqara integration."""

from enum import StrEnum

import probatio
from xiaomi_gateway import XiaomiGateway

from homeassistant.components import persistent_notification
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN


class XiaomiAqaraService(StrEnum):
    """Store keys for Xiaomi Aqara services."""

    ADD_DEVICE = "add_device"
    PLAY_RINGTONE = "play_ringtone"
    REMOVE_DEVICE = "remove_device"
    STOP_RINGTONE = "stop_ringtone"


class XiaomiAqaraServiceArgument(StrEnum):
    """Store keys for Xiaomi Aqara service arguments."""

    GW_MAC = "gw_mac"
    RINGTONE_ID = "ringtone_id"
    RINGTONE_VOL = "ringtone_vol"


SERVICE_SCHEMA_PLAY_RINGTONE = probatio.Schema(
    {
        probatio.Required(XiaomiAqaraServiceArgument.RINGTONE_ID): probatio.All(
            probatio.Coerce(int), probatio.NotIn([9, 14, 15, 16, 17, 18, 19])
        ),
        probatio.Optional(XiaomiAqaraServiceArgument.RINGTONE_VOL): probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=0, max=100)
        ),
    }
)

SERVICE_SCHEMA_REMOVE_DEVICE = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): probatio.All(
            cv.string, probatio.Length(min=14, max=14)
        )
    }
)


def _play_ringtone_service(call: ServiceCall) -> None:
    """Service to play ringtone through Gateway."""
    ring_id = call.data.get(XiaomiAqaraServiceArgument.RINGTONE_ID)
    gateway: XiaomiGateway = call.data[XiaomiAqaraServiceArgument.GW_MAC]

    kwargs = {"mid": ring_id}

    if (ring_vol := call.data.get(XiaomiAqaraServiceArgument.RINGTONE_VOL)) is not None:
        kwargs["vol"] = ring_vol

    gateway.write_to_hub(gateway.sid, **kwargs)


def _stop_ringtone_service(call: ServiceCall) -> None:
    """Service to stop playing ringtone on Gateway."""
    gateway: XiaomiGateway = call.data[XiaomiAqaraServiceArgument.GW_MAC]
    gateway.write_to_hub(gateway.sid, mid=10000)


def _add_device_service(call: ServiceCall) -> None:
    """Service to add a new sub-device within the next 30 seconds."""
    gateway: XiaomiGateway = call.data[XiaomiAqaraServiceArgument.GW_MAC]
    gateway.write_to_hub(gateway.sid, join_permission="yes")
    persistent_notification.async_create(
        call.hass,
        (
            "Join permission enabled for 30 seconds! "
            "Please press the pairing button of the new device once."
        ),
        title="Xiaomi Aqara Gateway",
    )


def _remove_device_service(call: ServiceCall) -> None:
    """Service to remove a sub-device from the gateway."""
    device_id = call.data.get(CommonServiceArgument.DEVICE_ID)
    gateway: XiaomiGateway = call.data[XiaomiAqaraServiceArgument.GW_MAC]
    gateway.write_to_hub(gateway.sid, remove_device=device_id)


def setup_services(hass: HomeAssistant) -> None:
    """Register the Xiaomi Aqara services."""
    gateway_only_schema = _add_gateway_to_schema(hass, probatio.Schema({}))

    hass.services.register(
        DOMAIN,
        XiaomiAqaraService.PLAY_RINGTONE,
        _play_ringtone_service,
        schema=_add_gateway_to_schema(hass, SERVICE_SCHEMA_PLAY_RINGTONE),
    )

    hass.services.register(
        DOMAIN,
        XiaomiAqaraService.STOP_RINGTONE,
        _stop_ringtone_service,
        schema=gateway_only_schema,
    )

    hass.services.register(
        DOMAIN,
        XiaomiAqaraService.ADD_DEVICE,
        _add_device_service,
        schema=gateway_only_schema,
    )

    hass.services.register(
        DOMAIN,
        XiaomiAqaraService.REMOVE_DEVICE,
        _remove_device_service,
        schema=_add_gateway_to_schema(hass, SERVICE_SCHEMA_REMOVE_DEVICE),
    )


def _add_gateway_to_schema(
    hass: HomeAssistant, schema: probatio.Schema
) -> probatio.Schema:
    """Extend a probatio schema with a gateway validator."""

    def gateway(sid: str) -> XiaomiGateway:
        """Convert sid to a gateway."""
        sid = str(sid).replace(":", "").lower()

        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            entry_gateway = entry.runtime_data
            if entry_gateway.sid == sid:
                return entry_gateway

        raise probatio.Invalid(f"Unknown gateway sid {sid}")

    kwargs = {}
    gateways = [
        entry.runtime_data for entry in hass.config_entries.async_loaded_entries(DOMAIN)
    ]

    # If the user has only 1 gateway, make it the default for services.
    if len(gateways) == 1:
        kwargs["default"] = gateways[0].sid

    return schema.extend(
        {probatio.Required(XiaomiAqaraServiceArgument.GW_MAC, **kwargs): gateway}
    )
