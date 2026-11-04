"""Services for the Lovelace integration."""

from homeassistant.config import (
    async_hass_config_yaml,
    async_process_component_and_handle_errors,
)
from homeassistant.const import CONF_RESOURCES
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.loader import async_get_integration

from . import resources
from .const import (
    DOMAIN,
    LOVELACE_DATA,
    MODE_YAML,
    RESOURCE_RELOAD_SERVICE_SCHEMA,
    SERVICE_RELOAD_RESOURCES,
)


async def _reload_resources_service_handler(service_call: ServiceCall) -> None:
    """Reload yaml resources."""
    hass = service_call.hass
    if hass.data[LOVELACE_DATA].resource_mode != MODE_YAML:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="resources_not_yaml_mode",
        )
    try:
        conf = await async_hass_config_yaml(hass)
    except HomeAssistantError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="failed_to_reload",
        ) from err

    integration = await async_get_integration(hass, DOMAIN)

    config = await async_process_component_and_handle_errors(hass, conf, integration)

    if config is None:
        raise HomeAssistantError("Config validation failed")

    resource_collection = await resources.create_yaml_resource_col(
        hass, config[DOMAIN].get(CONF_RESOURCES)
    )
    hass.data[LOVELACE_DATA].resources = resource_collection


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Lovelace integration."""
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD_RESOURCES,
        _reload_resources_service_handler,
        schema=RESOURCE_RELOAD_SERVICE_SCHEMA,
    )
