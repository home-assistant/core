"""Services for the Home Assistant integration."""

import asyncio
from collections.abc import Callable, Coroutine
import itertools as it
import logging
from typing import Any

import probatio

from homeassistant import config as conf_util, core_config
from homeassistant.auth.permissions.const import CAT_ENTITIES, POLICY_CONTROL
from homeassistant.components import persistent_notification
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import (
    ATTR_ELEVATION,
    ATTR_ENTITY_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    SERVICE_RELOAD,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    callback,
    split_entity_id,
)
from homeassistant.exceptions import HomeAssistantError, Unauthorized, UnknownUser
from homeassistant.helpers import config_validation as cv, recorder, restore_state
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.service import (
    async_extract_config_entry_ids,
    async_register_admin_service,
)
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)
from homeassistant.helpers.template import async_load_custom_templates

from .const import DATA_STOP_HANDLER, DOMAIN, HomeAssistantService

ATTR_ENTRY_ID = "entry_id"
ATTR_SAFE_MODE = "safe_mode"

_LOGGER = logging.getLogger(__name__)

SCHEMA_UPDATE_ENTITY = probatio.Schema({ATTR_ENTITY_ID: cv.entity_ids})
SCHEMA_RELOAD_CONFIG_ENTRY = probatio.All(
    probatio.Schema(
        {
            probatio.Optional(ATTR_ENTRY_ID): str,
            **cv.ENTITY_SERVICE_FIELDS,
        },
    ),
    probatio.AtLeastOne(ATTR_ENTRY_ID, *cv.ENTITY_SERVICE_FIELDS),
)
SCHEMA_RESTART = probatio.Schema(
    {probatio.Optional(ATTR_SAFE_MODE, default=False): bool}
)

SHUTDOWN_SERVICES = (HomeAssistantService.STOP, HomeAssistantService.RESTART)


async def _async_save_persistent_states(service: ServiceCall) -> None:
    """Handle calls to homeassistant.save_persistent_states."""
    hass = service.hass
    await restore_state.RestoreStateData.async_save_persistent_states(hass)


async def _async_handle_turn_service(service: ServiceCall) -> None:
    """Handle calls to homeassistant.turn_on/off."""
    hass = service.hass
    referenced = async_extract_referenced_entity_ids(
        hass, TargetSelection(service.data)
    )
    all_referenced = referenced.referenced | referenced.indirectly_referenced

    # Generic turn on/off method requires entity id
    if not all_referenced:
        _LOGGER.error(
            "The service homeassistant.%s cannot be called without a target",
            service.service,
        )
        return

    # Group entity_ids by domain. groupby requires sorted data.
    by_domain = it.groupby(
        sorted(all_referenced), lambda item: split_entity_id(item)[0]
    )

    tasks: list[Coroutine[Any, Any, ServiceResponse]] = []
    unsupported_entities: set[str] = set()

    for domain, ent_ids in by_domain:
        # This leads to endless loop.
        if domain == DOMAIN:
            _LOGGER.warning(
                "Called service homeassistant.%s with invalid entities %s",
                service.service,
                ", ".join(ent_ids),
            )
            continue

        if not hass.services.has_service(domain, service.service):
            unsupported_entities.update(set(ent_ids) & referenced.referenced)
            continue

        # Create a new dict for this call
        data = dict(service.data)

        # ent_ids is a generator, convert it to a list.
        data[ATTR_ENTITY_ID] = list(ent_ids)

        tasks.append(
            hass.services.async_call(
                domain,
                service.service,
                data,
                blocking=True,
                context=service.context,
            )
        )

    if unsupported_entities:
        _LOGGER.warning(
            "The service homeassistant.%s does not support entities %s",
            service.service,
            ", ".join(sorted(unsupported_entities)),
        )

    if tasks:
        await asyncio.gather(*tasks)


async def _async_handle_core_service(call: ServiceCall) -> None:
    """Service handler for handling core services."""
    hass = call.hass
    stop_handler: Callable[[HomeAssistant, bool], Coroutine[Any, Any, None]]

    if call.service in SHUTDOWN_SERVICES and recorder.async_migration_in_progress(hass):
        _LOGGER.error(
            "The system cannot %s while a database upgrade is in progress",
            call.service,
        )
        raise HomeAssistantError(
            f"The system cannot {call.service} while a database upgrade is in progress."
        )

    if call.service == HomeAssistantService.STOP:
        stop_handler = hass.data[DATA_STOP_HANDLER]
        await stop_handler(hass, False)
        return

    errors = await conf_util.async_check_ha_config_file(hass)

    if errors:
        _LOGGER.error(
            "The system cannot %s because the configuration is not valid: %s",
            call.service,
            errors,
        )
        persistent_notification.async_create(
            hass,
            "Config error. See [the logs](/config/logs) for details.",
            "Config validating",
            f"{DOMAIN}.check_config",
        )
        raise HomeAssistantError(
            f"The system cannot {call.service} "
            f"because the configuration is not valid: {errors}"
        )

    if call.service == HomeAssistantService.RESTART:
        if call.data[ATTR_SAFE_MODE]:
            await conf_util.async_enable_safe_mode(hass)
        stop_handler = hass.data[DATA_STOP_HANDLER]
        await stop_handler(hass, True)


async def _async_handle_update_service(call: ServiceCall) -> None:
    """Service handler for updating an entity."""
    hass = call.hass
    if call.context.user_id:
        user = await hass.auth.async_get_user(call.context.user_id)

        if user is None:
            raise UnknownUser(
                context=call.context,
                permission=POLICY_CONTROL,
                user_id=call.context.user_id,
            )

        for entity in call.data[ATTR_ENTITY_ID]:
            if not user.permissions.check_entity(entity, POLICY_CONTROL):
                raise Unauthorized(
                    context=call.context,
                    permission=POLICY_CONTROL,
                    user_id=call.context.user_id,
                    perm_category=CAT_ENTITIES,
                )

    tasks = [async_update_entity(hass, entity) for entity in call.data[ATTR_ENTITY_ID]]

    if tasks:
        await asyncio.gather(*tasks)


async def _async_handle_reload_config(call: ServiceCall) -> None:
    """Service handler for reloading core config."""
    hass = call.hass
    try:
        conf = await conf_util.async_hass_config_yaml(hass)
    except (HomeAssistantError, FileNotFoundError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="core_config_reload_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    # auth only processed during startup
    await core_config.async_process_ha_core_config(hass, conf.get(DOMAIN) or {})


async def _async_set_location(call: ServiceCall) -> None:
    """Service handler to set location."""
    hass = call.hass
    service_data = {
        "latitude": call.data[ATTR_LATITUDE],
        "longitude": call.data[ATTR_LONGITUDE],
    }

    if (elevation := call.data.get(ATTR_ELEVATION)) is not None:
        service_data["elevation"] = elevation

    await hass.config.async_update(**service_data)


async def _async_handle_reload_templates(call: ServiceCall) -> None:
    """Service handler to reload custom Jinja."""
    hass = call.hass
    await async_load_custom_templates(hass)


async def _async_handle_reload_config_entry(call: ServiceCall) -> None:
    """Service handler for reloading a config entry."""
    hass = call.hass
    reload_entries: set[str] = set()
    if ATTR_ENTRY_ID in call.data:
        reload_entries.add(call.data[ATTR_ENTRY_ID])
    if TargetSelection(call.data).has_any_target:
        _LOGGER.warning(
            "Reloading a config entry by target is deprecated and will stop "
            "working in Home Assistant 2027.4, please specify the config entry "
            "to reload in the 'entry_id' parameter instead"
        )
    reload_entries.update(await async_extract_config_entry_ids(call))
    if not reload_entries:
        raise ValueError("There were no matching config entries to reload")
    await asyncio.gather(
        *(
            hass.config_entries.async_reload(config_entry_id)
            for config_entry_id in reload_entries
        )
    )


async def _async_handle_reload_all(call: ServiceCall) -> None:
    """Service handler for calling all integration reload services.

    Calls all reload services on all active domains, which triggers the
    reload of YAML configurations for the domain that support it.

    Additionally, it also calls the `homeasssitant.reload_core_config`
    service, as that reloads the core YAML configuration, the
    `frontend.reload_themes` service that reloads the themes, and the
    `homeassistant.reload_custom_templates` service that reloads any custom
    jinja into memory.

    We only do so, if there are no configuration errors.
    """
    hass = call.hass

    if errors := await conf_util.async_check_ha_config_file(hass):
        _LOGGER.error(
            "The system cannot reload because the configuration is not valid: %s",
            errors,
        )
        raise HomeAssistantError(
            "Cannot quick reload all YAML configurations because the "
            f"configuration is not valid: {errors}"
        )

    services = hass.services.async_services_internal()
    tasks = [
        hass.services.async_call(
            domain, SERVICE_RELOAD, context=call.context, blocking=True
        )
        for domain, domain_services in services.items()
        if domain != NOTIFY_DOMAIN and SERVICE_RELOAD in domain_services
    ] + [
        hass.services.async_call(domain, service, context=call.context, blocking=True)
        for domain, service in (
            (DOMAIN, HomeAssistantService.RELOAD_CORE_CONFIG),
            ("frontend", "reload_themes"),
            (DOMAIN, HomeAssistantService.RELOAD_CUSTOM_TEMPLATES),
        )
    ]

    await asyncio.gather(*tasks)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Home Assistant integration."""
    hass.services.async_register(
        DOMAIN,
        HomeAssistantService.SAVE_PERSISTENT_STATES,
        _async_save_persistent_states,
    )

    service_schema = probatio.Schema(
        {ATTR_ENTITY_ID: cv.entity_ids}, extra=probatio.ALLOW_EXTRA
    )

    hass.services.async_register(
        DOMAIN,
        HomeAssistantService.TURN_OFF,
        _async_handle_turn_service,
        schema=service_schema,
    )
    hass.services.async_register(
        DOMAIN,
        HomeAssistantService.TURN_ON,
        _async_handle_turn_service,
        schema=service_schema,
    )
    hass.services.async_register(
        DOMAIN,
        HomeAssistantService.TOGGLE,
        _async_handle_turn_service,
        schema=service_schema,
    )

    async_register_admin_service(
        hass, DOMAIN, HomeAssistantService.STOP, _async_handle_core_service
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        HomeAssistantService.RESTART,
        _async_handle_core_service,
        SCHEMA_RESTART,
    )
    async_register_admin_service(
        hass, DOMAIN, HomeAssistantService.CHECK_CONFIG, _async_handle_core_service
    )
    hass.services.async_register(
        DOMAIN,
        HomeAssistantService.UPDATE_ENTITY,
        _async_handle_update_service,
        schema=SCHEMA_UPDATE_ENTITY,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        HomeAssistantService.RELOAD_CORE_CONFIG,
        _async_handle_reload_config,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        HomeAssistantService.SET_LOCATION,
        _async_set_location,
        probatio.Schema(
            {
                probatio.Required(ATTR_LATITUDE): cv.latitude,
                probatio.Required(ATTR_LONGITUDE): cv.longitude,
                probatio.Optional(ATTR_ELEVATION): probatio.Coerce(int),
            }
        ),
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        HomeAssistantService.RELOAD_CUSTOM_TEMPLATES,
        _async_handle_reload_templates,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        HomeAssistantService.RELOAD_CONFIG_ENTRY,
        _async_handle_reload_config_entry,
        schema=SCHEMA_RELOAD_CONFIG_ENTRY,
    )

    async_register_admin_service(
        hass, DOMAIN, HomeAssistantService.RELOAD_ALL, _async_handle_reload_all
    )
