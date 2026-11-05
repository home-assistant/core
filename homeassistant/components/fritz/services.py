"""Services for Fritz integration."""

from enum import StrEnum
from typing import cast

from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzActionFailedError,
    FritzConnectionException,
    FritzServiceError,
)
from fritzconnection.lib.fritzwlan import DEFAULT_PASSWORD_LENGTH
import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers.service import (
    async_extract_config_entry_ids,
    async_get_device_and_config_entry,
    async_register_admin_service,
)
from homeassistant.util.json import JsonArrayType, JsonObjectType

from .const import (
    CONF_ALLOW_MESH_INFO_NON_ADMIN,
    DEFAULT_CONF_ALLOW_MESH_INFO_NON_ADMIN,
    DOMAIN,
    FRITZ_EXCEPTIONS,
    LOGGER,
    MeshRoles,
)
from .coordinator import FritzConfigEntry


class FritzService(StrEnum):
    """Store keys for FRITZ!Box Tools services."""

    SET_GUEST_WIFI_PASSWORD = "set_guest_wifi_password"
    DIAL = "dial"
    GET_MESH_INFO = "get_mesh_info"


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

SERVICE_SCHEMA_GET_MESH_INFO = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): str,
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


async def _async_get_mesh_info(service_call: ServiceCall) -> ServiceResponse:
    """Return the most recent mesh info for targeted config entry."""
    _, target_entry = async_get_device_and_config_entry(
        service_call.hass, DOMAIN, service_call.data["device_id"]
    )
    hass = service_call.hass
    user_id = service_call.context.user_id
    if user_id is not None:
        user = await hass.auth.async_get_user(user_id)
        is_admin = user is not None and user.is_admin
    else:
        is_admin = True
    allow_non_admin = target_entry.options.get(
        CONF_ALLOW_MESH_INFO_NON_ADMIN, DEFAULT_CONF_ALLOW_MESH_INFO_NON_ADMIN
    )

    if not is_admin and not allow_non_admin:
        raise Unauthorized(
            context=service_call.context,
            permission="call_service",
            user_id=service_call.context.user_id,
        )

    avm_wrapper = target_entry.runtime_data
    if avm_wrapper.mesh_role == MeshRoles.SLAVE:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_mesh_info_slave_node",
        )

    # Not cached by the coordinator if device tracking or mesh discovery is disabled
    if (mesh_topology := avm_wrapper.mesh_topology_raw) is None:
        if not avm_wrapper.fritz_status.device_has_mesh_support:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_mesh_info_no_mesh_support",
            )
        try:
            topology = await hass.async_add_executor_job(
                avm_wrapper.fritz_hosts.get_mesh_topology
            )
        except FritzActionError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_mesh_info_slave_node",
            ) from ex
        except FRITZ_EXCEPTIONS as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_mesh_info_fetch_failed",
            ) from ex
        if not topology or not isinstance(topology, dict):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_mesh_info_fetch_failed",
            )
        mesh_topology = cast(JsonObjectType, topology)

    if (hosts_attributes := avm_wrapper.hosts_attributes_raw) is None:
        try:
            hosts_attributes = cast(
                JsonArrayType,
                await hass.async_add_executor_job(
                    avm_wrapper.fritz_hosts.get_hosts_attributes
                ),
            )
        except FRITZ_EXCEPTIONS as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_hosts_info_fetch_failed",
            ) from ex

    return {
        "mesh_topology": mesh_topology,
        "hosts_attributes": hosts_attributes,
    }


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
    hass.services.async_register(
        DOMAIN,
        FritzService.GET_MESH_INFO,
        _async_get_mesh_info,
        SERVICE_SCHEMA_GET_MESH_INFO,
        supports_response=SupportsResponse.ONLY,
    )
