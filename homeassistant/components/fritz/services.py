"""Services for Fritz integration."""

from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzActionFailedError,
    FritzConnectionException,
    FritzServiceError,
)
from fritzconnection.lib.fritzwlan import DEFAULT_PASSWORD_LENGTH
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import (
    async_extract_config_entry_ids,
    async_register_admin_service,
)

from .const import CONF_ALLOW_MESH_INFO_NON_ADMIN, DOMAIN, LOGGER, MeshRoles
from .coordinator import FritzConfigEntry

SERVICE_SET_GUEST_WIFI_PW = "set_guest_wifi_password"
SERVICE_SCHEMA_SET_GUEST_WIFI_PW = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Optional("password"): vol.Length(min=8, max=63),
        vol.Optional("length"): vol.Range(min=8, max=63),
    }
)
SERVICE_DIAL = "dial"
SERVICE_SCHEMA_DIAL = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("number"): str,
        vol.Required("max_ring_seconds"): vol.Range(min=1, max=300),
    }
)

SERVICE_GET_MESH_INFO = "get_mesh_info"
SERVICE_SCHEMA_GET_MESH_INFO = vol.Schema(
    {
        vol.Required("device_id"): str,
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
                service_call.data.get("password"),
                service_call.data.get("length", DEFAULT_PASSWORD_LENGTH),
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
                service_call.data["number"],
                max_ring_seconds=service_call.data["max_ring_seconds"],
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

    target_entry = target_entries[0]

    user_id = service_call.context.user_id
    if user_id is None:
        is_admin = True
    else:
        is_admin = False
        user = await service_call.hass.auth.async_get_user(user_id)
        if user is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_mesh_info_not_permitted",
            )
        is_admin = user.is_admin

    if not is_admin and not target_entry.options.get(
        CONF_ALLOW_MESH_INFO_NON_ADMIN, False
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="service_mesh_info_not_permitted",
        )

    avm_wrapper = target_entry.runtime_data

    if (mesh_topology := avm_wrapper.mesh_topology_raw) is None:
        if not avm_wrapper.fritz_status.device_has_mesh_support:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_mesh_info_no_mesh_support",
            )
        if avm_wrapper.mesh_role == MeshRoles.SLAVE:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_mesh_info_slave_node",
            )
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_mesh_info_fetch_failed",
        )

    if (hosts_attributes := avm_wrapper.hosts_attributes_raw) is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_hosts_info_fetch_failed",
        )

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
        SERVICE_SET_GUEST_WIFI_PW,
        _async_set_guest_wifi_password,
        SERVICE_SCHEMA_SET_GUEST_WIFI_PW,
    )
    hass.services.async_register(DOMAIN, SERVICE_DIAL, _async_dial, SERVICE_SCHEMA_DIAL)
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_MESH_INFO,
        _async_get_mesh_info,
        SERVICE_SCHEMA_GET_MESH_INFO,
        supports_response=SupportsResponse.ONLY,
    )
