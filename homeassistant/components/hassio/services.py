"""Set up Supervisor services."""

from collections.abc import Awaitable, Callable
from enum import StrEnum
import json
import re
from typing import Any

from aiohasupervisor import SupervisorClient, SupervisorError
from aiohasupervisor.models import (
    Folder,
    FullBackupOptions,
    FullRestoreOptions,
    PartialBackupOptions,
    PartialRestoreOptions,
)
import probatio

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    issue_registry as ir,
    selector,
)
from homeassistant.helpers.service import (
    async_get_device_and_config_entry,
    async_register_admin_service,
)
from homeassistant.util.dt import now

from .const import DOMAIN, ISSUE_KEY_LEGACY_HOMEASSISTANT_FOLDER, SupervisorEntityModel
from .handler import get_supervisor_client


class HassioService(StrEnum):
    """Store keys for Supervisor services."""

    ADDON_RESTART = "addon_restart"
    ADDON_START = "addon_start"
    ADDON_STDIN = "addon_stdin"
    ADDON_STOP = "addon_stop"
    APP_RESTART = "app_restart"
    APP_START = "app_start"
    APP_STDIN = "app_stdin"
    APP_STOP = "app_stop"
    BACKUP_FULL = "backup_full"
    BACKUP_PARTIAL = "backup_partial"
    HOST_REBOOT = "host_reboot"
    HOST_SHUTDOWN = "host_shutdown"
    MOUNT_RELOAD = "mount_reload"
    RESTORE_FULL = "restore_full"
    RESTORE_PARTIAL = "restore_partial"


class HassioServiceArgument(StrEnum):
    """Store keys for Supervisor service arguments."""

    ADDON = "addon"
    ADDONS = "addons"
    APP = "app"
    APPS = "apps"
    COMPRESSED = "compressed"
    FOLDERS = "folders"
    HOMEASSISTANT = "homeassistant"
    HOMEASSISTANT_EXCLUDE_DATABASE = "homeassistant_exclude_database"
    INPUT = "input"
    LOCATION = "location"
    NAME = "name"
    PASSWORD = "password"
    SLUG = "slug"


VALID_ADDON_SLUG = probatio.Match(re.compile(r"^[-_.A-Za-z0-9]+$"))

# Legacy alias used by the Supervisor API for the homeassistant flag, kept
# for backwards compatibility with existing automations.
LEGACY_FOLDER_HOMEASSISTANT = "homeassistant"


def _normalize_partial_options_data(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Map legacy aliases used by both partial backup and partial restore handlers."""
    if HassioServiceArgument.APPS in data:
        data[HassioServiceArgument.ADDONS] = data.pop(HassioServiceArgument.APPS)
    if HassioServiceArgument.FOLDERS in data:
        folders: set[Any] = set(data[HassioServiceArgument.FOLDERS])
        if LEGACY_FOLDER_HOMEASSISTANT in folders:
            folders.discard(LEGACY_FOLDER_HOMEASSISTANT)
            if data.get(HassioServiceArgument.HOMEASSISTANT) is False:
                raise ServiceValidationError(
                    f"{HassioServiceArgument.HOMEASSISTANT}=False conflicts with the legacy "
                    f"{LEGACY_FOLDER_HOMEASSISTANT!r} entry in {HassioServiceArgument.FOLDERS}"
                )
            data[HassioServiceArgument.HOMEASSISTANT] = True
            ir.async_create_issue(
                hass,
                DOMAIN,
                ISSUE_KEY_LEGACY_HOMEASSISTANT_FOLDER,
                breaks_in_ha_version="2026.12.0",
                is_fixable=True,
                is_persistent=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_KEY_LEGACY_HOMEASSISTANT_FOLDER,
            )
        if folders:
            data[HassioServiceArgument.FOLDERS] = folders
        else:
            data.pop(HassioServiceArgument.FOLDERS)
    return data


SCHEMA_NO_DATA = probatio.Schema({})

SCHEMA_ADDON = probatio.Schema(
    {probatio.Required(HassioServiceArgument.ADDON): VALID_ADDON_SLUG}
)

SCHEMA_ADDON_STDIN = SCHEMA_ADDON.extend(
    {probatio.Required(HassioServiceArgument.INPUT): probatio.Any(dict, cv.string)}
)

SCHEMA_APP = probatio.Schema(
    {probatio.Required(HassioServiceArgument.APP): VALID_ADDON_SLUG}
)

SCHEMA_APP_STDIN = SCHEMA_APP.extend(
    {probatio.Required(HassioServiceArgument.INPUT): probatio.Any(dict, cv.string)}
)

SCHEMA_BACKUP_FULL = probatio.Schema(
    {
        probatio.Optional(
            HassioServiceArgument.NAME,
            default=lambda: now().strftime("%Y-%m-%d %H:%M:%S"),
        ): cv.string,
        probatio.Optional(HassioServiceArgument.PASSWORD): cv.string,
        probatio.Optional(HassioServiceArgument.COMPRESSED): cv.boolean,
        probatio.Optional(HassioServiceArgument.LOCATION): probatio.All(
            cv.string, lambda v: None if v == "/backup" else v
        ),
        probatio.Optional(
            HassioServiceArgument.HOMEASSISTANT_EXCLUDE_DATABASE
        ): cv.boolean,
    }
)

SCHEMA_BACKUP_PARTIAL = SCHEMA_BACKUP_FULL.extend(
    {
        probatio.Optional(HassioServiceArgument.HOMEASSISTANT): cv.boolean,
        probatio.Optional(HassioServiceArgument.FOLDERS): probatio.All(
            probatio.EnsureList(),
            [probatio.Any(LEGACY_FOLDER_HOMEASSISTANT, probatio.Coerce(Folder))],
            probatio.Unique(),
            probatio.Coerce(set),
        ),
        probatio.Exclusive(HassioServiceArgument.APPS, "apps_or_addons"): probatio.All(
            probatio.EnsureList(),
            [VALID_ADDON_SLUG],
            probatio.Unique(),
            probatio.Coerce(set),
        ),
        # Legacy "addons", "apps" is preferred
        probatio.Exclusive(
            HassioServiceArgument.ADDONS, "apps_or_addons"
        ): probatio.All(
            probatio.EnsureList(),
            [VALID_ADDON_SLUG],
            probatio.Unique(),
            probatio.Coerce(set),
        ),
    }
)

SCHEMA_RESTORE_FULL = probatio.Schema(
    {
        probatio.Required(HassioServiceArgument.SLUG): cv.slug,
        probatio.Optional(HassioServiceArgument.PASSWORD): cv.string,
    }
)

SCHEMA_RESTORE_PARTIAL = SCHEMA_RESTORE_FULL.extend(
    {
        probatio.Optional(HassioServiceArgument.HOMEASSISTANT): cv.boolean,
        probatio.Optional(HassioServiceArgument.FOLDERS): probatio.All(
            probatio.EnsureList(),
            [probatio.Any(LEGACY_FOLDER_HOMEASSISTANT, probatio.Coerce(Folder))],
            probatio.Unique(),
            probatio.Coerce(set),
        ),
        probatio.Exclusive(HassioServiceArgument.APPS, "apps_or_addons"): probatio.All(
            probatio.EnsureList(),
            [VALID_ADDON_SLUG],
            probatio.Unique(),
            probatio.Coerce(set),
        ),
        # Legacy "addons", "apps" is preferred
        probatio.Exclusive(
            HassioServiceArgument.ADDONS, "apps_or_addons"
        ): probatio.All(
            probatio.EnsureList(),
            [VALID_ADDON_SLUG],
            probatio.Unique(),
            probatio.Coerce(set),
        ),
    }
)

SCHEMA_MOUNT_RELOAD = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): selector.DeviceSelector(
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
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Supervisor services."""
    supervisor_client = get_supervisor_client(hass)
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
        HassioService.APP_START: ("start", supervisor_client.addons.start_addon),
        HassioService.APP_RESTART: ("restart", supervisor_client.addons.restart_addon),
        HassioService.APP_STOP: ("stop", supervisor_client.addons.stop_addon),
    }

    async def async_simple_app_service_handler(service: ServiceCall) -> None:
        """Handles app services which only take a slug and have no response."""
        action, api_method = simple_app_services[service.service]
        app_slug = service.data[HassioServiceArgument.APP]

        try:
            await api_method(app_slug)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to {action} app {app_slug}: {err}"
            ) from err

    for service in simple_app_services:
        async_register_admin_service(
            hass, DOMAIN, service, async_simple_app_service_handler, schema=SCHEMA_APP
        )

    async def async_app_stdin_service_handler(service: ServiceCall) -> None:
        """Handles app stdin service."""
        app_slug = service.data[HassioServiceArgument.APP]
        data: dict | str = service.data[HassioServiceArgument.INPUT]

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

    async_register_admin_service(
        hass,
        DOMAIN,
        HassioService.APP_STDIN,
        async_app_stdin_service_handler,
        schema=SCHEMA_APP_STDIN,
    )

    # LEGACY - Register equivalent addon services for compatibility
    simple_addon_services: dict[str, tuple[str, Callable[[str], Awaitable[None]]]] = {
        HassioService.ADDON_START: ("start", supervisor_client.addons.start_addon),
        HassioService.ADDON_RESTART: (
            "restart",
            supervisor_client.addons.restart_addon,
        ),
        HassioService.ADDON_STOP: ("stop", supervisor_client.addons.stop_addon),
    }

    async def async_simple_addon_service_handler(service: ServiceCall) -> None:
        """Handles addon services which only take a slug and have no response."""
        action, api_method = simple_addon_services[service.service]
        addon_slug = service.data[HassioServiceArgument.ADDON]

        try:
            await api_method(addon_slug)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to {action} app {addon_slug}: {err}"
            ) from err

    for service in simple_addon_services:
        async_register_admin_service(
            hass,
            DOMAIN,
            service,
            async_simple_addon_service_handler,
            schema=SCHEMA_ADDON,
        )

    async def async_addon_stdin_service_handler(service: ServiceCall) -> None:
        """Handles addon stdin service."""
        addon_slug = service.data[HassioServiceArgument.ADDON]
        data: dict | str = service.data[HassioServiceArgument.INPUT]

        # See explanation for why we make strings into json
        # in async_app_stdin_service_handler
        data = json.dumps(data)
        payload = data.encode(encoding="utf-8")

        try:
            await supervisor_client.addons.write_addon_stdin(addon_slug, payload)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to write stdin to app {addon_slug}: {err}"
            ) from err

    async_register_admin_service(
        hass,
        DOMAIN,
        HassioService.ADDON_STDIN,
        async_addon_stdin_service_handler,
        schema=SCHEMA_ADDON_STDIN,
    )


@callback
def async_register_host_services(
    hass: HomeAssistant, supervisor_client: SupervisorClient
) -> None:
    """Register host services."""
    simple_host_services: dict[str, tuple[str, Callable[[], Awaitable[None]]]] = {
        HassioService.HOST_REBOOT: ("reboot", supervisor_client.host.reboot),
        HassioService.HOST_SHUTDOWN: ("shutdown", supervisor_client.host.shutdown),
    }

    async def async_simple_host_service_handler(service: ServiceCall) -> None:
        """Handler for host services that take no input and return no response."""
        action, api_method = simple_host_services[service.service]
        try:
            await api_method()
        except SupervisorError as err:
            raise HomeAssistantError(f"Failed to {action} the host: {err}") from err

    for service in simple_host_services:
        async_register_admin_service(
            hass,
            DOMAIN,
            service,
            async_simple_host_service_handler,
            schema=SCHEMA_NO_DATA,
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

    async_register_admin_service(
        hass,
        DOMAIN,
        HassioService.BACKUP_FULL,
        async_full_backup_service_handler,
        schema=SCHEMA_BACKUP_FULL,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def async_partial_backup_service_handler(
        service: ServiceCall,
    ) -> ServiceResponse:
        """Handler for create partial backup service. Returns the new backup's ID."""
        data = _normalize_partial_options_data(hass, service.data.copy())
        options = PartialBackupOptions(**data)

        try:
            backup = await supervisor_client.backups.partial_backup(options)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to create partial backup {options.name}: {err}"
            ) from err

        return {"backup": backup.slug}

    async_register_admin_service(
        hass,
        DOMAIN,
        HassioService.BACKUP_PARTIAL,
        async_partial_backup_service_handler,
        schema=SCHEMA_BACKUP_PARTIAL,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def async_full_restore_service_handler(service: ServiceCall) -> None:
        """Handler for full restore service."""
        backup_slug = service.data[HassioServiceArgument.SLUG]
        options: FullRestoreOptions | None = None
        if HassioServiceArgument.PASSWORD in service.data:
            options = FullRestoreOptions(
                password=service.data[HassioServiceArgument.PASSWORD]
            )

        try:
            await supervisor_client.backups.full_restore(backup_slug, options)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to full restore from backup {backup_slug}: {err}"
            ) from err

    async_register_admin_service(
        hass,
        DOMAIN,
        HassioService.RESTORE_FULL,
        async_full_restore_service_handler,
        schema=SCHEMA_RESTORE_FULL,
    )

    async def async_partial_restore_service_handler(service: ServiceCall) -> None:
        """Handler for partial restore service."""
        data = service.data.copy()
        backup_slug = data.pop(HassioServiceArgument.SLUG)
        data = _normalize_partial_options_data(hass, data)
        options = PartialRestoreOptions(**data)

        try:
            await supervisor_client.backups.partial_restore(backup_slug, options)
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Failed to partial restore from backup {backup_slug}: {err}"
            ) from err

    async_register_admin_service(
        hass,
        DOMAIN,
        HassioService.RESTORE_PARTIAL,
        async_partial_restore_service_handler,
        schema=SCHEMA_RESTORE_PARTIAL,
    )


@callback
def async_register_network_storage_services(
    hass: HomeAssistant, supervisor_client: SupervisorClient
) -> None:
    """Register network storage (or mount) services."""

    async def async_mount_reload(service: ServiceCall) -> None:
        """Handle service calls for Hass.io."""
        # A mount is always a main device, and the check below reads its model
        device, _ = async_get_device_and_config_entry(
            hass, DOMAIN, service.data[ATTR_DEVICE_ID], include_child_devices=False
        )

        if device.name is None or device.model != SupervisorEntityModel.MOUNT:
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

    async_register_admin_service(
        hass,
        DOMAIN,
        HassioService.MOUNT_RELOAD,
        async_mount_reload,
        SCHEMA_MOUNT_RELOAD,
    )
