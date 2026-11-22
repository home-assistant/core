"""Services for Fritz integration."""

from enum import StrEnum

from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzActionFailedError,
    FritzConnectionException,
    FritzServiceError,
)
from fritzconnection.lib.fritzwlan import DEFAULT_PASSWORD_LENGTH
import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import (
    async_extract_config_entry_ids,
    async_register_admin_service,
)

from .const import DOMAIN, LOGGER
from .coordinator import FritzConfigEntry


class FritzService(StrEnum):
    """Store keys for FRITZ!Box Tools services."""

    SET_GUEST_WIFI_PASSWORD = "set_guest_wifi_password"
    DIAL = "dial"


class FritzServiceArgument(StrEnum):
    """Store keys for FRITZ!Box Tools service arguments."""

    PASSWORD = "password"
    LENGTH = "length"
    NUMBER = "number"
    MAX_RING_SECONDS = "max_ring_seconds"


SERVICE_SCHEMA_SET_GUEST_WIFI_PW = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): str,
        probatio.Optional(FritzServiceArgument.PASSWORD): probatio.Length(
            min=8, max=63
        ),
        probatio.Optional(FritzServiceArgument.LENGTH): probatio.Range(min=8, max=63),
    }
)
SERVICE_SCHEMA_DIAL = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): str,
        probatio.Required(FritzServiceArgument.NUMBER): str,
        probatio.Required(FritzServiceArgument.MAX_RING_SECONDS): probatio.Range(
            min=1, max=300
        ),
    }
)


async def _async_set_guest_wifi_password(service_call: ServiceCall) -> None:
    """Call Fritz set guest wifi password service."""
    target_entry_ids = await async_extract_config_entry_ids(service_call)
    target_entries: list[FritzConfigEntry] = [
        loaded_entry
        for loaded_entry in service_call.hass.config_entries.async_loaded_entries(
            DOMAIN
        )
        if loaded_entry.entry_id in target_entry_ids
    ]

    if not target_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
            translation_placeholders={"service": service_call.service},
        )

    for target_entry in target_entries:
        LOGGER.debug("Executing service %s", service_call.service)
        avm_wrapper = target_entry.runtime_data
        try:
            await avm_wrapper.async_trigger_set_guest_password(
                service_call.data.get(FritzServiceArgument.PASSWORD),
                service_call.data.get(
                    FritzServiceArgument.LENGTH, DEFAULT_PASSWORD_LENGTH
                ),
            )
        except (FritzServiceError, FritzActionError) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="service_parameter_unknown"
            ) from ex
        except FritzConnectionException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="service_not_supported"
            ) from ex


async def _async_dial(service_call: ServiceCall) -> None:
    """Call Fritz dial service."""
    target_entry_ids = await async_extract_config_entry_ids(service_call)
    target_entries: list[FritzConfigEntry] = [
        loaded_entry
        for loaded_entry in service_call.hass.config_entries.async_loaded_entries(
            DOMAIN
        )
        if loaded_entry.entry_id in target_entry_ids
    ]

    if not target_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
            translation_placeholders={"service": service_call.service},
        )

    for target_entry in target_entries:
        LOGGER.debug("Executing service %s", service_call.service)
        avm_wrapper = target_entry.runtime_data
        try:
            await avm_wrapper.async_trigger_dial(
                service_call.data[FritzServiceArgument.NUMBER],
                max_ring_seconds=service_call.data[
                    FritzServiceArgument.MAX_RING_SECONDS
                ],
            )
        except (FritzServiceError, FritzActionError) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="service_parameter_unknown"
            ) from ex
        except FritzActionFailedError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="service_dial_failed"
            ) from ex
        except FritzConnectionException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="service_not_supported"
            ) from ex


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Fritz integration."""

    async_register_admin_service(
        hass,
        DOMAIN,
        FritzService.SET_GUEST_WIFI_PASSWORD,
        _async_set_guest_wifi_password,
        SERVICE_SCHEMA_SET_GUEST_WIFI_PW,
    )
    hass.services.async_register(
        DOMAIN, FritzService.DIAL, _async_dial, SERVICE_SCHEMA_DIAL
    )
