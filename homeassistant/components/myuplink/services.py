"""Action services for the myUplink integration."""

from typing import cast

from aiohttp import ClientError
import probatio

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import AnyDeviceEntry
from homeassistant.helpers.service import (
    async_get_device_and_config_entry,
    async_register_admin_service,
)

from .const import DOMAIN

ATTR_DATAPOINT_ID = "datapoint_id"
ATTR_VALUE = "value"

SERVICE_SET_DATAPOINT = "set_datapoint"
SERVICE_SET_DATAPOINT_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): str,
        probatio.Required(ATTR_DATAPOINT_ID): cv.positive_int,
        probatio.Required(ATTR_VALUE): cv.string,
    },
)


async def _get_myuplink_device_id(
    hass: HomeAssistant, device_entry: AnyDeviceEntry
) -> str:
    """Extract the myUplink device ID from the device identifier."""

    try:
        myuplink_device_id = next(
            (
                identifier[1]
                for identifier in cast(dr.DeviceEntry, device_entry).identifiers
                if identifier[0] == DOMAIN
            ),
            None,
        )
    except AttributeError:
        myuplink_device_id = None

    if myuplink_device_id is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target",
        )
    return myuplink_device_id


async def async_set_datapoint(call: ServiceCall) -> None:
    """Handle the set_datapoint service call."""

    datapoint_id: str = call.data.get(ATTR_DATAPOINT_ID, "")
    value: str = call.data.get(ATTR_VALUE, "")

    device_entry, config_entry = async_get_device_and_config_entry(
        call.hass, DOMAIN, call.data[ATTR_DEVICE_ID]
    )

    api = config_entry.runtime_data.api
    device_id = await _get_myuplink_device_id(call.hass, device_entry)

    try:
        await api.async_set_device_points(device_id, data={datapoint_id: str(value)})
    except ClientError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_datapoint_error",
            translation_placeholders={
                "device": device_id,
                "point": datapoint_id,
                "value": value,
            },
        ) from err


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_DATAPOINT,
        async_set_datapoint,
        schema=SERVICE_SET_DATAPOINT_SCHEMA,
    )
