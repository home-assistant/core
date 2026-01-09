"""Switch entities for Unraid integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, STATE_CONTAINER_RUNNING, VM_RUNNING_STATES
from .models import DockerContainer, VmDomain

if TYPE_CHECKING:
    from unraid_api import UnraidClient

    from homeassistant.core import HomeAssistant

    from . import UnraidConfigEntry
    from .coordinator import UnraidSystemCoordinator, UnraidSystemData

_LOGGER = logging.getLogger(__name__)

# Number of parallel update requests
PARALLEL_UPDATES = 1


class UnraidSwitchEntity(SwitchEntity):
    """Base class for Unraid switch entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: UnraidSystemCoordinator,
        api_client: UnraidClient,
        server_uuid: str,
        server_name: str,
        resource_id: str,
        name: str,
        server_info: dict | None = None,
    ) -> None:
        """Initialize switch entity."""
        self.coordinator = coordinator
        self.api_client = api_client
        self._server_uuid = server_uuid
        self._server_name = server_name
        self._attr_unique_id = f"{server_uuid}_{resource_id}"
        self._attr_name = name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, server_uuid)},
            "name": server_name,
            "manufacturer": server_info.get("manufacturer") if server_info else None,
            "model": server_info.get("model") if server_info else None,
            "serial_number": (
                server_info.get("serial_number") if server_info else None
            ),
            "sw_version": server_info.get("sw_version") if server_info else None,
            "hw_version": server_info.get("hw_version") if server_info else None,
            "configuration_url": (
                server_info.get("configuration_url") if server_info else None
            ),
        }

    @property
    def available(self) -> bool:
        """Return whether entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher when added to Home Assistant."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_write_ha_state)
        )


class DockerContainerSwitch(UnraidSwitchEntity):
    """Docker container control switch."""

    _attr_translation_key = "docker_container"

    def __init__(
        self,
        coordinator: UnraidSystemCoordinator,
        api_client: UnraidClient,
        server_uuid: str,
        server_name: str,
        container: DockerContainer,
    ) -> None:
        """Initialize docker container switch."""
        # Container IDs are ephemeral (change on container update/recreate)
        # Use container NAME for unique_id to maintain entity stability
        self._container_name = container.name.lstrip("/")
        # Store the current container ID for API calls (start/stop)
        # This will be updated when the container is recreated
        self._container_id = container.id
        self._cached_container: DockerContainer | None = None
        self._cache_data_id: int | None = None
        super().__init__(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid=server_uuid,
            server_name=server_name,
            # Use container NAME for stable unique_id (not ID which changes)
            resource_id=f"container_switch_{self._container_name}",
            name=f"Container {self._container_name}",
        )

    def _get_container(self) -> DockerContainer | None:
        """Get current container from coordinator data with caching.

        Looks up container by NAME (stable) not ID (ephemeral).
        Also updates the stored container_id if it changed (e.g., after update).
        """
        data: UnraidSystemData | None = self.coordinator.data
        if data is None:
            return None

        # Use cache if data object hasn't changed (same coordinator refresh)
        data_id = id(data)
        if (
            self._cache_data_id is not None
            and data_id == self._cache_data_id
            and self._cached_container is not None
        ):
            return self._cached_container

        # Build lookup dict by NAME for O(1) access (name is stable, ID is not)
        container_map = {c.name.lstrip("/"): c for c in data.containers}
        self._cached_container = container_map.get(self._container_name)
        self._cache_data_id = data_id

        # Update container ID if it changed (after container update/recreate)
        if self._cached_container is not None:
            self._container_id = self._cached_container.id

        return self._cached_container

    @property
    def is_on(self) -> bool:
        """Return True if container is running."""
        container = self._get_container()
        if container is None:
            return False
        return container.state == STATE_CONTAINER_RUNNING

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes, filtering out None values."""
        container = self._get_container()
        if container is None:
            return {}
        attrs: dict[str, Any] = {
            "status": container.state,
        }
        if container.image is not None:
            attrs["image"] = container.image
        if container.web_ui_url is not None:
            attrs["web_ui_url"] = container.web_ui_url
        if container.icon_url is not None:
            attrs["icon_url"] = container.icon_url
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start container."""
        try:
            await self.api_client.start_container(self._container_id)
            _LOGGER.debug("Started Docker container: %s", self._container_id)
        except Exception as err:
            _LOGGER.error("Failed to start Docker container: %s", err)
            raise HomeAssistantError(f"Failed to start container: {err}") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop container."""
        try:
            await self.api_client.stop_container(self._container_id)
            _LOGGER.debug("Stopped Docker container: %s", self._container_id)
        except Exception as err:
            _LOGGER.error("Failed to stop Docker container: %s", err)
            raise HomeAssistantError(f"Failed to stop container: {err}") from err


class VirtualMachineSwitch(UnraidSwitchEntity):
    """Virtual machine control switch."""

    _attr_translation_key = "virtual_machine"

    def __init__(
        self,
        coordinator: UnraidSystemCoordinator,
        api_client: UnraidClient,
        server_uuid: str,
        server_name: str,
        vm: VmDomain,
    ) -> None:
        """Initialize virtual machine switch."""
        # VM names are stable across restarts; IDs may not be
        # Use VM NAME for unique_id to maintain entity stability
        self._vm_name = vm.name
        # Store the current VM ID for API calls (start/stop)
        self._vm_id = vm.id
        self._cached_vm: VmDomain | None = None
        self._cache_data_id: int | None = None
        super().__init__(
            coordinator=coordinator,
            api_client=api_client,
            server_uuid=server_uuid,
            server_name=server_name,
            # Use VM NAME for stable unique_id (not ID which may change)
            resource_id=f"vm_switch_{self._vm_name}",
            name=f"VM {vm.name}",
        )

    def _get_vm(self) -> VmDomain | None:
        """Get current VM from coordinator data with caching.

        Looks up VM by NAME (stable) not ID (may be ephemeral).
        Also updates the stored vm_id if it changed.
        """
        data: UnraidSystemData | None = self.coordinator.data
        if data is None:
            return None

        # Use cache if data object hasn't changed (same coordinator refresh)
        data_id = id(data)
        if (
            self._cache_data_id is not None
            and data_id == self._cache_data_id
            and self._cached_vm is not None
        ):
            return self._cached_vm

        # Build lookup dict by NAME for O(1) access (name is stable)
        vm_map = {v.name: v for v in data.vms}
        self._cached_vm = vm_map.get(self._vm_name)
        self._cache_data_id = data_id

        # Update the VM ID if it changed
        if self._cached_vm is not None:
            self._vm_id = self._cached_vm.id

        return self._cached_vm

    @property
    def is_on(self) -> bool:
        """Return True if VM is running or idle."""
        vm = self._get_vm()
        if vm is None:
            return False
        return vm.state in VM_RUNNING_STATES

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes, filtering out None values."""
        vm = self._get_vm()
        if vm is None:
            return {}
        attrs: dict[str, Any] = {
            "state": vm.state,
        }
        if vm.memory is not None:
            attrs["memory"] = vm.memory
        if vm.vcpu is not None:
            attrs["vcpu"] = vm.vcpu
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start VM."""
        try:
            await self.api_client.start_vm(self._vm_id)
            _LOGGER.debug("Started VM: %s", self._vm_id)
        except Exception as err:
            _LOGGER.error("Failed to start VM: %s", err)
            raise HomeAssistantError(f"Failed to start VM: {err}") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop VM."""
        try:
            await self.api_client.stop_vm(self._vm_id)
            _LOGGER.debug("Stopped VM: %s", self._vm_id)
        except Exception as err:
            _LOGGER.error("Failed to stop VM: %s", err)
            raise HomeAssistantError(f"Failed to stop VM: {err}") from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities."""
    _LOGGER.debug("Setting up Unraid switch platform")

    # Get coordinators and API client from runtime_data (HA 2024.4+ pattern)
    runtime_data = entry.runtime_data
    system_coordinator = runtime_data.system_coordinator
    api_client = runtime_data.api_client
    server_info = runtime_data.server_info

    # Server info is now a flat dict with uuid, name, manufacturer, etc.
    server_uuid = server_info.get("uuid", "unknown")
    server_name = server_info.get("name", entry.data.get("host", "Unraid"))

    entities: list[UnraidSwitchEntity] = []

    # Add Docker container switches (only when Docker service is running)
    if system_coordinator.data and system_coordinator.data.containers:
        _LOGGER.debug(
            "Docker service running with %d container(s), creating switches",
            len(system_coordinator.data.containers),
        )
        entities.extend(
            DockerContainerSwitch(
                system_coordinator, api_client, server_uuid, server_name, container
            )
            for container in system_coordinator.data.containers
        )
    else:
        _LOGGER.debug(
            "Docker service not running or no containers on %s",
            server_name,
        )

    # Add VM switches (only when VM/libvirt service is running)
    if system_coordinator.data and system_coordinator.data.vms:
        _LOGGER.debug(
            "VM service running with %d VM(s), creating switches",
            len(system_coordinator.data.vms),
        )
        entities.extend(
            VirtualMachineSwitch(
                system_coordinator, api_client, server_uuid, server_name, vm
            )
            for vm in system_coordinator.data.vms
        )
    else:
        _LOGGER.debug(
            "VM service not available or no VMs on %s, skipping VM switches",
            server_name,
        )

    _LOGGER.debug("Adding %d switch entities", len(entities))
    async_add_entities(entities)
