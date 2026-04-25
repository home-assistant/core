"""Set up Supervisor services."""

from collections.abc import Awaitable, Callable
import json
import re
from typing import Any

from aiohasupervisor import SupervisorClient, SupervisorError
from aiohasupervisor.models import (
    FullBackupOptions,
    FullRestoreOptions,
    PartialBackupOptions,
    PartialRestoreOptions,
)
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_NAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    async_get_hass_or_none,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    selector,
)
from homeassistant.util.dt import now

from .const import (
    ATTR_ADDON,
    ATTR_ADDONS,
    ATTR_APP,
    ATTR_APPS,
    ATTR_COMPRESSED,
    ATTR_FOLDERS,
    ATTR_HOMEASSISTANT,
    ATTR_HOMEASSISTANT_EXCLUDE_DATABASE,
    ATTR_INPUT,
    ATTR_LOCATION,
    ATTR_PASSWORD,
    ATTR_SLUG,
    DOMAIN,
    MAIN_COORDINATOR,
    SupervisorEntityModel,
)
from .coordinator import HassioMainDataUpdateCoordinator, get_addons_info

SERVICE_ADDON_START = "addon_start"
SERVICE_ADDON_STOP = "addon_stop"
SERVICE_ADDON_RESTART = "addon_restart"
SERVICE_ADDON_STDIN = "addon_stdin"
SERVICE_APP_START = "app_start"
SERVICE_APP_STOP = "app_stop"
SERVICE_APP_RESTART = "app_restart"
SERVICE_APP_STDIN = "app_stdin"
SERVICE_HOST_SHUTDOWN = "host_shutdown"
SERVICE_HOST_REBOOT = "host_reboot"
SERVICE_BACKUP_FULL = "backup_full"
SERVICE_BACKUP_PARTIAL = "backup_partial"
SERVICE_RESTORE_FULL = "restore_full"
SERVICE_RESTORE_PARTIAL = "restore_partial"
SERVICE_MOUNT_RELOAD = "mount_reload"


VALID_ADDON_SLUG = vol.Match(re.compile(r"^[-_.A-Za-z0-9]+$"))


def valid_addon(value: Any) -> str:
    """Validate value is a valid addon slug."""
    value = VALID_ADDON_SLUG(value)
    hass = async_get_hass_or_none()

    if hass and (addons := get_addons_info(hass)) is not None and value not in addons:
        raise vol.Invalid("Not a valid app slug")
    return value


SCHEMA_NO_DATA = vol.Schema({})

SCHEMA_ADDON = vol.Schema({vol.Required(ATTR_ADDON): valid_addon})

SCHEMA_ADDON_STDIN = SCHEMA_ADDON.extend(
    {vol.Required(ATTR_INPUT): vol.Any(dict, cv.string)}
)

SCHEMA_APP = vol.Schema({vol.Required(ATTR_APP): valid_addon})

SCHEMA_APP_STDIN = SCHEMA_APP.extend(
    {vol.Required(ATTR_INPUT): vol.Any(dict, cv.string)}
)

SCHEMA_BACKUP_FULL = vol.Schema(
    {
        vol.Optional(
            ATTR_NAME, default=lambda: now().strftime("%Y-%m-%d %H:%M:%S")
        ): cv.string,
        vol.Optional(ATTR_PASSWORD): cv.string,
        vol.Optional(ATTR_COMPRESSED): cv.boolean,
        vol.Optional(ATTR_LOCATION): vol.All(
            cv.string, lambda v: None if v == "/backup" else v
        ),
        vol.Optional(ATTR_HOMEASSISTANT_EXCLUDE_DATABASE): cv.boolean,
    }
)

SCHEMA_BACKUP_PARTIAL = SCHEMA_BACKUP_FULL.extend(
    {
        vol.Optional(ATTR_HOMEASSISTANT): cv.boolean,
        vol.Optional(ATTR_FOLDERS): vol.All(
            cv.ensure_list, [cv.string], vol.Unique(), vol.Coerce(set)
        ),
        vol.Exclusive(ATTR_APPS, "apps_or_addons"): vol.All(
            cv.ensure_list, [VALID_ADDON_SLUG], vol.Unique(), vol.Coerce(set)
        ),
        # Legacy "addons", "apps" is preferred
        vol.Exclusive(ATTR_ADDONS, "apps_or_addons"): vol.All(
            cv.ensure_list, [VALID_ADDON_SLUG], vol.Unique(), vol.Coerce(set)
        ),
    }
)

SCHEMA_RESTORE_FULL = vol.Schema(
    {
        vol.Required(ATTR_SLUG): cv.slug,
        vol.Optional(ATTR_PASSWORD): cv.string,
    }
)

SCHEMA_RESTORE_PARTIAL = SCHEMA_RESTORE_FULL.extend(
    {
        vol.Optional(ATTR_HOMEASSISTANT): cv.boolean,
        vol.Optional(ATTR_FOLDERS): vol.All(
            cv.ensure_list, [cv.string], vol.Unique(), vol.Coerce(set)
        ),
        vol.Exclusive(ATTR_APPS, "apps_or_addons"): vol.All(
            cv.ensure_list, [VALID_ADDON_SLUG], vol.Unique(), vol.Coerce(set)
        ),
        # Legacy "addons", "apps" is preferred
        vol.Exclusive(ATTR_ADDONS, "apps_or_addons"): vol.All(
            cv.ensure_list, [VALID_ADDON_SLUG], vol.Unique(), vol.Coerce(set)
        ),
    }
)

SCHEMA_MOUNT_RELOAD = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): selector.DeviceSelector(
            selector.DeviceSelectorConfig(
                filter=selector.DeviceFilterSelectorConfig(
                    integration=DOMAIN,
                    model=SupervisorEntityModel.MOUNT,
                )
            )
        )
    }
)


@callback
def async_setup_services(
    hass: HomeAssistant, supervisor_client: SupervisorClient
) -> None:
    """Register the Supervisor services."""
    async_register_app_services(hass, supervisor_client)
    async_register_host_services(hass, supervisor_client)
    async_register_backup_restore_services(hass, supervisor_client)
    async_register_network_storage_services(hass, supervisor_client)


@callback
def async_register_app_services(
    hass: HomeAssistant, supervisor_client: SupervisorClient
) -> None:
    """Register app services."""
    simple_app_services: dict[str, tuple[str, Callable[[str], Awaitable[None]]]] = {
        SERVICE_APP_START: ("start", supervisor_client.addons.start_addon),
        SERVICE_APP_RESTART: ("restart", supervisor_client.addons.restart_addon),
        SERVICE_APP_STOP: ("stop", supervisor_client.addons.stop_addon),
    }

    async def async_simple_app_service_handler(service: ServiceCall) -> None:
        """Handles app services which only take a slug and have no response."""
        action, api_method = simple_app_services[service.service]
        app_slug = service.data[ATTR_APP]

        try:
            await api_method(app_slug)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to {action} app {app_slug}: {err}"
            ) from err

    for service in simple_app_services:
        hass.services.async_register(
            DOMAIN, service, async_simple_app_service_handler, schema=SCHEMA_APP
        )

    async def async_app_stdin_service_handler(service: ServiceCall) -> None:
        """Handles app stdin service."""
        app_slug = service.data[ATTR_APP]
        data: dict | str = service.data[ATTR_INPUT]

        # For backwards compatibility the payload here must be valid json
        # This is sensible when a dictionary is provided, it must be serialized
        # If user provides a string though, we wrap it in quotes before encoding
        # This is purely for legacy reasons, Supervisor has no json requirement
        # Supervisor just hands the raw request as binary to the container
        data = json.dumps(data)
        payload = data.encode(encoding="utf-8")

        try:
            await supervisor_client.addons.write_addon_stdin(app_slug, payload)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to write stdin to app {app_slug}: {err}"
            ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_APP_STDIN,
        async_app_stdin_service_handler,
        schema=SCHEMA_APP_STDIN,
    )

    # LEGACY - Register equivalent addon services for compatibility
    simple_addon_services: dict[str, tuple[str, Callable[[str], Awaitable[None]]]] = {
        SERVICE_ADDON_START: ("start", supervisor_client.addons.start_addon),
        SERVICE_ADDON_RESTART: ("restart", supervisor_client.addons.restart_addon),
        SERVICE_ADDON_STOP: ("stop", supervisor_client.addons.stop_addon),
    }

    async def async_simple_addon_service_handler(service: ServiceCall) -> None:
        """Handles addon services which only take a slug and have no response."""
        action, api_method = simple_addon_services[service.service]
        addon_slug = service.data[ATTR_ADDON]

        try:
            await api_method(addon_slug)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to {action} app {addon_slug}: {err}"
            ) from err

    for service in simple_addon_services:
        hass.services.async_register(
            DOMAIN, service, async_simple_addon_service_handler, schema=SCHEMA_ADDON
        )

    async def async_addon_stdin_service_handler(service: ServiceCall) -> None:
        """Handles addon stdin service."""
        addon_slug = service.data[ATTR_ADDON]
        data: dict | str = service.data[ATTR_INPUT]

        # See explanation for why we make strings into json in async_app_stdin_service_handler
        data = json.dumps(data)
        payload = data.encode(encoding="utf-8")

        try:
            await supervisor_client.addons.write_addon_stdin(addon_slug, payload)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to write stdin to app {addon_slug}: {err}"
            ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADDON_STDIN,
        async_addon_stdin_service_handler,
        schema=SCHEMA_ADDON_STDIN,
    )


@callback
def async_register_host_services(
    hass: HomeAssistant, supervisor_client: SupervisorClient
) -> None:
    """Register host services."""
    simple_host_services: dict[str, tuple[str, Callable[[], Awaitable[None]]]] = {
        SERVICE_HOST_REBOOT: ("reboot", supervisor_client.host.reboot),
        SERVICE_HOST_SHUTDOWN: ("shutdown", supervisor_client.host.shutdown),
    }

    async def async_simple_host_service_handler(service: ServiceCall) -> None:
        """Handler for host services that take no input and return no response."""
        action, api_method = simple_host_services[service.service]
        try:
            await api_method()
        except SupervisorError as err:
            raise HomeAssistantError(f"Failed to {action} the host: {err}") from err

    for service in simple_host_services:
        hass.services.async_register(
            DOMAIN, service, async_simple_host_service_handler, schema=SCHEMA_NO_DATA
        )


@callback
def async_register_backup_restore_services(
    hass: HomeAssistant, supervisor_client: SupervisorClient
) -> None:
    """Register backup and restore services."""

    async def async_full_backup_service_handler(
        service: ServiceCall,
    ) -> ServiceResponse:
        """Handler for create full backup service. Returns the new backup's ID."""
        options = FullBackupOptions(**service.data)
        try:
            backup = await supervisor_client.backups.full_backup(options)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to create full backup {options.name}: {err}"
            ) from err

        return {"backup": backup.slug}

    hass.services.async_register(
        DOMAIN,
        SERVICE_BACKUP_FULL,
        async_full_backup_service_handler,
        schema=SCHEMA_BACKUP_FULL,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def async_partial_backup_service_handler(
        service: ServiceCall,
    ) -> ServiceResponse:
        """Handler for create partial backup service. Returns the new backup's ID."""
        data = service.data.copy()
        if ATTR_APPS in data:
            data[ATTR_ADDONS] = data.pop(ATTR_APPS)
        options = PartialBackupOptions(**data)

        try:
            backup = await supervisor_client.backups.partial_backup(options)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to create partial backup {options.name}: {err}"
            ) from err

        return {"backup": backup.slug}

    hass.services.async_register(
        DOMAIN,
        SERVICE_BACKUP_PARTIAL,
        async_partial_backup_service_handler,
        schema=SCHEMA_BACKUP_PARTIAL,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def async_full_restore_service_handler(service: ServiceCall) -> None:
        """Handler for full restore service."""
        backup_slug = service.data[ATTR_SLUG]
        options: FullRestoreOptions | None = None
        if ATTR_PASSWORD in service.data:
            options = FullRestoreOptions(password=service.data[ATTR_PASSWORD])

        try:
            await supervisor_client.backups.full_restore(backup_slug, options)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to full restore from backup {backup_slug}: {err}"
            ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTORE_FULL,
        async_full_restore_service_handler,
        schema=SCHEMA_RESTORE_FULL,
    )

    async def async_partial_restore_service_handler(service: ServiceCall) -> None:
        """Handler for partial restore service."""
        data = service.data.copy()
        backup_slug = data.pop(ATTR_SLUG)
        if ATTR_APPS in data:
            data[ATTR_ADDONS] = data.pop(ATTR_APPS)
        options = PartialRestoreOptions(**data)

        try:
            await supervisor_client.backups.partial_restore(backup_slug, options)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to partial restore from backup {backup_slug}: {err}"
            ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTORE_PARTIAL,
        async_partial_restore_service_handler,
        schema=SCHEMA_RESTORE_PARTIAL,
    )


@callback
def async_register_network_storage_services(
    hass: HomeAssistant, supervisor_client: SupervisorClient
) -> None:
    """Register network storage (or mount) services."""
    dev_reg = dr.async_get(hass)

    async def async_mount_reload(service: ServiceCall) -> None:
        """Handle service calls for Hass.io."""
        coordinator: HassioMainDataUpdateCoordinator | None = None

        if (device := dev_reg.async_get(service.data[ATTR_DEVICE_ID])) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="mount_reload_unknown_device_id",
            )

        if (
            device.name is None
            or device.model != SupervisorEntityModel.MOUNT
            or (coordinator := hass.data.get(MAIN_COORDINATOR)) is None
            or coordinator.entry_id not in device.config_entries
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="mount_reload_invalid_device",
            )

        try:
            await supervisor_client.mounts.reload_mount(device.name)
        except SupervisorError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="mount_reload_error",
                translation_placeholders={"name": device.name, "error": str(error)},
            ) from error

    hass.services.async_register(
        DOMAIN, SERVICE_MOUNT_RELOAD, async_mount_reload, SCHEMA_MOUNT_RELOAD
    )
