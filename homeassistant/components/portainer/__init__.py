"""The Portainer integration."""

from collections import defaultdict
from datetime import timedelta
import logging
from types import MappingProxyType
from typing import TYPE_CHECKING

from pyportainer import Portainer, PortainerImageWatcher
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerError,
    PortainerTimeoutError,
)

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_URL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import (
    AnyDeviceEntry,
    ChildDeviceEntry,
    DeviceEntry,
)
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .const import API_MAX_RETRIES, DOMAIN, SUBENTRY_TYPE_ENVIRONMENT
from .coordinator import (
    PortainerCoordinator,
    PortainerDockerDiskSpaceCoordinator,
    PortainerSystemVersionCoordinator,
)
from .services import async_setup_services

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type PortainerConfigEntry = ConfigEntry[PortainerCoordinator]

_LOGGER = logging.getLogger(__name__)


async def _async_update_listener(
    hass: HomeAssistant, entry: PortainerConfigEntry
) -> None:
    """Reload the entry when it, or one of its environment subentries, changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> None:
    """Set up Portainer from a config entry."""

    session = async_create_clientsession(
        hass=hass, verify_ssl=entry.data[CONF_VERIFY_SSL]
    )

    client = Portainer(
        api_url=entry.data[CONF_URL],
        api_key=entry.data[CONF_API_TOKEN],
        session=session,
        request_timeout=10,
        max_retries=API_MAX_RETRIES,
    )
    watcher = PortainerImageWatcher(client, interval=timedelta(hours=24))

    coordinator = PortainerCoordinator(hass, entry, client)
    coordinator.watcher = watcher
    await coordinator.async_config_entry_first_refresh()

    docker_system_df_client = Portainer(
        api_url=entry.data[CONF_URL],
        api_key=entry.data[CONF_API_TOKEN],
        session=session,
        request_timeout=120,
        max_retries=API_MAX_RETRIES,
    )

    docker_disk_space_coordinator = PortainerDockerDiskSpaceCoordinator(
        hass, entry, docker_system_df_client
    )
    coordinator.docker_disk_space = docker_disk_space_coordinator

    system_version_coordinator = PortainerSystemVersionCoordinator(hass, entry, client)
    coordinator.system_version = system_version_coordinator

    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register the endpoint and stack devices up front so that container, stack and
    # volume entities can deterministically resolve them as their via device when
    # their platforms are set up below, regardless of platform/entity add order.
    coordinator.async_register_endpoint_and_stack_devices(
        coordinator.data,
        set(coordinator.data),
        {
            (endpoint_id, stack_name, stack_data.stack.id)
            for endpoint_id, endpoint_data in coordinator.data.items()
            for stack_name, stack_data in endpoint_data.stacks.items()
        },
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    async def _defer_initial_refreshes(_: HomeAssistant) -> None:
        """Defer the first refresh until Home Assistant has started."""
        hass.async_create_task(
            docker_disk_space_coordinator.async_refresh(),
            "portainer_docker_disk_space_initial_refresh",
        )
        hass.async_create_task(
            system_version_coordinator.async_refresh(),
            "portainer_system_version_initial_refresh",
        )

    # On lower-end hardware, the DF endpoint can take long, and the version check
    # waits for GitHub. Do not block the setup, but defer both until HA has started.
    # Registered after the platforms, so the DF refresh sees the enabled entities.
    entry.async_on_unload(async_at_started(hass, _defer_initial_refreshes))

    @callback
    def _start_watcher(_hass: HomeAssistant) -> None:
        """Start the image watcher in the event loop."""
        watcher.start()

    @callback
    def _stop_watcher(_event: Event) -> None:
        """Stop the image watcher in the event loop."""
        watcher.stop()

    entry.async_on_unload(async_at_started(hass, _start_watcher))
    entry.async_on_unload(watcher.stop)
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_watcher)
    )

    @callback
    def _start_event_listeners(_hass: HomeAssistant) -> None:
        """Start the Docker event listeners in the event loop."""
        coordinator.async_start_event_listeners()

    @callback
    def _stop_event_listeners(_event: Event) -> None:
        """Stop the Docker event listeners in the event loop."""
        coordinator.async_stop_event_listeners()

    # Defer the event listener, to avoid a thunderherd of connections during startup
    entry.async_on_unload(async_at_started(hass, _start_event_listeners))
    entry.async_on_unload(coordinator.async_stop_event_listeners)
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_event_listeners)
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Portainer integration."""
    async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> None:
    """Migrate old entry."""

    if entry.version < 2:
        data = dict(entry.data)
        data[CONF_URL] = data.pop(CONF_HOST)
        data[CONF_API_TOKEN] = data.pop(CONF_API_KEY)
        hass.config_entries.async_update_entry(entry=entry, data=data, version=2)

    if entry.version < 3:
        data = dict(entry.data)
        data[CONF_VERIFY_SSL] = True
        hass.config_entries.async_update_entry(entry=entry, data=data, version=3)

    if entry.version < 4:
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        for device in devices:
            # This means it's an endpoint. This can be skipped,
            # we're only interested in the containers
            if device.via_device_id is None:
                continue

            parent_devices = device_registry.async_get(device.via_device_id)
            if TYPE_CHECKING:
                assert parent_devices is not None
            for parent_device in parent_devices.identifiers:
                if parent_device[0] == DOMAIN:
                    parent_device_identifiers = parent_device
                    break

            _LOGGER.debug("Parent device identifiers: %s", parent_device_identifiers)
            endpoint_id = parent_device_identifiers[1].split("_")[-1]
            _LOGGER.debug("Endpoint ID: %s", endpoint_id)
            current_identifier = next(iter(device.identifiers))
            _LOGGER.debug("Current identifier: %s", current_identifier)
            container = current_identifier[1].split("_", 1)[1]
            _LOGGER.debug("Container name: %s", container)
            new_identifier = f"{entry.entry_id}_{endpoint_id}_{container}"
            _LOGGER.debug("New identifier: %s", new_identifier)

            new_identifiers = set(device.identifiers)
            new_identifiers.add((DOMAIN, new_identifier))

            device_registry.async_update_device(
                device.id,
                new_identifiers=new_identifiers,
            )

            # Now also update the underlying entities with the new unique_attr_id
            entities_device = er.async_entries_for_device(
                entity_registry,
                device.id,
            )
            for entity in entities_device:
                _LOGGER.debug("Handling entity: %s", entity)
                # This time we also also have a rest tail (for instance _firefly_iii_db)
                _, _, rest_tail = entity.unique_id.split("_", 2)
                new_unique_id = f"{new_identifier}_{rest_tail}"
                _LOGGER.debug("New unique ID: %s", new_unique_id)
                entity_registry.async_update_entity(
                    entity_id=entity.entity_id, new_unique_id=new_unique_id
                )

        hass.config_entries.async_update_entry(entry=entry, version=4)

    if entry.version < 5:
        client = Portainer(
            api_url=entry.data[CONF_URL],
            api_key=entry.data[CONF_API_TOKEN],
            session=async_create_clientsession(
                hass=hass, verify_ssl=entry.data[CONF_VERIFY_SSL]
            ),
        )
        try:
            system_status = await client.portainer_system_status()
        except PortainerAuthenticationError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except PortainerConnectionError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except PortainerTimeoutError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
            ) from err
        except PortainerError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="instance_id_failed",
            ) from err

        hass.config_entries.async_update_entry(
            entry=entry,
            unique_id=system_status.instance_id,
            version=5,
        )

    if entry.minor_version < 2:
        _async_migrate_config_subentries(hass, entry)
        hass.config_entries.async_update_entry(entry=entry, minor_version=2)
        hass.config_entries.async_schedule_reload(entry.entry_id)

    if entry.minor_version < 3:
        _async_disable_disk_space_sensors(hass, entry)
        hass.config_entries.async_update_entry(entry=entry, minor_version=3)

    if entry.minor_version < 4:
        _async_migrate_container_entity_registry(hass, entry)
        hass.config_entries.async_update_entry(entry=entry, minor_version=4)


@callback
def _async_migrate_container_entity_registry(
    hass: HomeAssistant, entry: PortainerConfigEntry
) -> None:
    """Migrate container entity IDs to include their endpoint ID."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    entry_id_prefix = f"{entry.entry_id}_"
    entity_migrations: list[tuple[er.RegistryEntry, str, str]] = []

    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if device.model != "Container":
            continue

        endpoint_device: AnyDeviceEntry = device
        while True:
            parent_device_id = (
                endpoint_device.parent_device_id
                if isinstance(endpoint_device, ChildDeviceEntry)
                else endpoint_device.via_device_id
            )
            if parent_device_id is None:
                break
            parent_device = device_registry.async_get(parent_device_id)
            if parent_device is None:
                break
            endpoint_device = parent_device

        endpoint_id = None
        for domain, identifier in endpoint_device.identifiers:
            if domain != DOMAIN or not identifier.startswith(entry_id_prefix):
                continue
            suffix = identifier.removeprefix(entry_id_prefix)
            suffix = suffix.removeprefix("endpoint_")
            if suffix.isdigit():
                endpoint_id = suffix
                break
        if endpoint_id is None and device.config_subentry_id is not None:
            subentry = entry.subentries.get(device.config_subentry_id)
            if subentry is not None and (
                subentry.subentry_type == SUBENTRY_TYPE_ENVIRONMENT
                and subentry.unique_id is not None
                and subentry.unique_id.isdigit()
            ):
                endpoint_id = subentry.unique_id
        if endpoint_id is None:
            raise ValueError(
                f"Could not determine the endpoint for container device {device.id}"
            )

        # Retained legacy identifiers can look like IDs from another endpoint.
        container_prefix = f"{entry_id_prefix}{endpoint_id}_"
        container_names = [
            identifier.removeprefix(container_prefix)
            for domain, identifier in device.identifiers
            if domain == DOMAIN
            and identifier.startswith(container_prefix)
            and identifier.removeprefix(container_prefix)
        ]
        if not container_names:
            raise ValueError(
                f"Could not determine the name for container device {device.id}"
            )

        container_name = max(container_names, key=len)
        canonical_prefix = f"{container_prefix}{container_name}_"
        legacy_prefix = f"{entry_id_prefix}{container_name}_"
        for entity in er.async_entries_for_device(
            entity_registry,
            device.id,
            include_disabled_entities=True,
        ):
            if entity.unique_id.startswith(canonical_prefix):
                continue
            if not entity.unique_id.startswith(legacy_prefix):
                continue
            entity_migrations.append(
                (
                    entity,
                    device.id,
                    f"{canonical_prefix}{entity.unique_id.removeprefix(legacy_prefix)}",
                )
            )

    # A target can be another container's legacy ID when its name starts with an
    # endpoint ID. Migrate those longer IDs first to free the targets.
    for entity, device_id, new_unique_id in sorted(
        entity_migrations,
        key=lambda migration: len(migration[0].unique_id),
        reverse=True,
    ):
        if existing_entity_id := entity_registry.async_get_entity_id(
            entity.domain, DOMAIN, new_unique_id
        ):
            existing_entity = entity_registry.async_get(existing_entity_id)
            if (
                existing_entity_id != entity.entity_id
                and existing_entity
                and existing_entity.device_id == device_id
            ):
                entity_registry.async_remove(entity.entity_id)
                continue

        entity_registry.async_update_entity(
            entity_id=entity.entity_id,
            new_unique_id=new_unique_id,
        )


@callback
def _async_migrate_config_subentries(
    hass: HomeAssistant, entry: PortainerConfigEntry
) -> None:
    """Create subentries for the entry's environments."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    devices_by_endpoint_id: dict[str, list[DeviceEntry]] = defaultdict(list)
    for device in devices:
        for domain, identifier in device.identifiers:
            if domain != DOMAIN:
                continue
            candidate = (
                identifier.removeprefix(f"{entry.entry_id}_")
                .removeprefix("endpoint_")
                .split("_", 1)[0]
            )
            if candidate.isdigit():
                devices_by_endpoint_id[candidate].append(device)
                break

    for endpoint_id, endpoint_devices in devices_by_endpoint_id.items():
        endpoint_device = next(
            device for device in endpoint_devices if device.via_device_id is None
        )
        subentry = ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_ENVIRONMENT,
            title=endpoint_device.name or f"Endpoint {endpoint_id}",
            unique_id=endpoint_id,
            data=MappingProxyType({}),
        )
        hass.config_entries.async_add_subentry(entry, subentry)

        for device in endpoint_devices:
            # Re-point entities before moving the device: the entity registry
            # deletes any entity whose stored config_subentry_id doesn't
            # already match the device's new one when it's re-parented
            for reg_entry in er.async_entries_for_device(
                entity_registry, device.id, include_disabled_entities=True
            ):
                endpoint_prefix = f"{entry.entry_id}_{endpoint_id}_"
                if device.model == "Container" and not (
                    reg_entry.unique_id.startswith(endpoint_prefix)
                ):
                    # Older container unique IDs didn't include the endpoint
                    # ID, so identically named containers on different
                    # environments collided on the same entity. Entities
                    # already migrated by the v3->v4 step are endpoint-scoped
                    # and must be left as-is to avoid double-prefixing.
                    entity_registry.async_update_entity(
                        reg_entry.entity_id,
                        config_subentry_id=subentry.subentry_id,
                        new_unique_id=(
                            f"{endpoint_prefix}{reg_entry.unique_id.removeprefix(f'{entry.entry_id}_')}"
                        ),
                    )
                else:
                    entity_registry.async_update_entity(
                        reg_entry.entity_id,
                        config_subentry_id=subentry.subentry_id,
                    )
            device_registry.async_update_device(
                device.id,
                new_config_entry_id=entry.entry_id,
                new_config_subentry_id=subentry.subentry_id,
            )


# Fixed at the sensors that existed when they became opt-in.
_DISK_SPACE_TRANSLATION_KEYS = {
    "container_disk_usage_reclaimable",
    "container_disk_usage_total_size",
    "image_disk_usage_reclaimable",
    "image_disk_usage_total_size",
    "volume_disk_usage_total_size",
    "volume_size",
}


@callback
def _async_disable_disk_space_sensors(
    hass: HomeAssistant, entry: PortainerConfigEntry
) -> None:
    """Disable the disk space sensors, which became opt-in as Docker computes them slowly."""
    entity_registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if (
            reg_entry.domain == Platform.SENSOR
            and reg_entry.translation_key in _DISK_SPACE_TRANSLATION_KEYS
            and reg_entry.disabled_by in (None, er.RegistryEntryDisabler.DEVICE)
        ):
            entity_registry.async_update_entity(
                reg_entry.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
            )


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    device: AnyDeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    coordinator = entry.runtime_data
    valid_identifiers: set[tuple[str, str]] = set()

    # The Portainer integration creates devices for both
    # endpoints and containers. That's why we're doing it double
    valid_identifiers.update(
        (DOMAIN, f"{entry.entry_id}_{endpoint_id}") for endpoint_id in coordinator.data
    )

    valid_identifiers.update(
        (DOMAIN, f"{entry.entry_id}_{endpoint_id}_{container_name}")
        for endpoint_id, endpoint in coordinator.data.items()
        for container_name in endpoint.containers
    )

    return not device.identifiers.intersection(valid_identifiers)
