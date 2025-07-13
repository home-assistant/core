"""Service calls for the Tessie integration."""

from aiohttp import ClientResponseError
from tessie_api import share

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SERVICE_SHARE


def async_get_device_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> dr.DeviceEntry | None:
    """Get the device entry related to a service call."""
    device_id = call.data[CONF_DEVICE_ID]
    device_registry = dr.async_get(hass)
    return device_registry.async_get(device_id)


def async_get_config_for_device(
    hass: HomeAssistant, device_entry: dr.DeviceEntry
) -> ConfigEntry | None:
    """Get the config entry related to a device entry."""
    for entry_id in device_entry.config_entries:
        if entry := hass.config_entries.async_get_entry(entry_id):
            if entry.domain == DOMAIN:
                return entry
    return None


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Teslemetry services."""

    async def service_share(call: ServiceCall) -> None:
        device_id = call.data[CONF_DEVICE_ID]
        content = call.data["content"]

        if (device := async_get_device_for_service_call(hass, call)) is not None and (
            config_entry := async_get_config_for_device(hass, device)
        ) is not None:
            api_key = config_entry.data[CONF_ACCESS_TOKEN]
            session = async_get_clientsession(hass)
            try:
                response = await share(
                    session=session,
                    vin=device.serial_number,
                    api_key=api_key,
                    value=content,
                )
            except ClientResponseError as e:
                raise HomeAssistantError from e
            if response["result"] is False:
                name: str = getattr(device, "name", device.id)
                reason: str = response.get("reason", "unknown")
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key=reason.replace(" ", "_"),
                    translation_placeholders={"name": name},
                )
        else:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_device",
                translation_placeholders={"device_id": device_id},
            )

    hass.services.async_register(DOMAIN, SERVICE_SHARE, service_share)
