"""Base entities for the Daikin Onecta integration."""

from collections.abc import Awaitable, Callable, Iterable, Iterator
from typing import Never, override

from daikin_onecta.client import OnectaClient
from daikin_onecta.models import Characteristic, ManagementPoint

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import (
    ChildDeviceInfo,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice, management_point_device_info
from .discovery import scalar_platform_for_point
from .utils import account_device_identifier, account_identifier

EntityIdChecker = Callable[[Platform, str], bool]


class _DaikinOnectaCoordinatorEntity(CoordinatorEntity[OnectaDataUpdateCoordinator]):
    """Share coordinator state updates."""

    def update_state(self) -> None:
        """Refresh entity state from the coordinator model."""

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.update_state()
        self.async_write_ha_state()


def add_entities_on_coordinator_update(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    coordinator: OnectaDataUpdateCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    create_entities: Callable[[EntityIdChecker], Iterable[Entity]],
) -> None:
    """Add newly available entities whenever the cloud model changes."""
    added_unique_ids: set[str] = set()
    registry = er.async_get(hass)
    last_cloud_update_sequence: int | None = None

    def already_known(platform: Platform, unique_id: str) -> bool:
        if unique_id in added_unique_ids:
            return True
        entity_id = registry.async_get_entity_id(platform.value, DOMAIN, unique_id)
        return (
            entity_id is not None
            and (entity_entry := registry.async_get(entity_id)) is not None
            and entity_entry.disabled
        )

    @callback
    def add_new_entities() -> None:
        nonlocal last_cloud_update_sequence
        if last_cloud_update_sequence == coordinator.cloud_update_sequence:
            return
        last_cloud_update_sequence = coordinator.cloud_update_sequence
        entities = list(create_entities(already_known))
        if entities:
            for entity in entities:
                unique_id = entity.unique_id
                if unique_id is None:
                    continue

                def remove_unique_id(unique_id: str = unique_id) -> None:
                    added_unique_ids.discard(unique_id)

                added_unique_ids.add(unique_id)
                entity.async_on_remove(remove_unique_id)
            async_add_entities(entities)

    add_new_entities()
    config_entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


def present_devices(
    coordinator: OnectaDataUpdateCoordinator,
) -> Iterator[DaikinOnectaDevice]:
    """Yield gateway devices present in the latest cloud response."""
    if coordinator.data is not None:
        yield from (
            device for device in coordinator.data.values() if device.present_in_cloud
        )


def iter_management_points(
    coordinator: OnectaDataUpdateCoordinator,
) -> Iterator[tuple[DaikinOnectaDevice, ManagementPoint]]:
    """Yield every management point on a currently present gateway."""
    for device in present_devices(coordinator):
        for management_point in device.device.management_points:
            yield device, management_point


def management_point_unique_id(gateway_id: str, embedded_id: str, *suffix: str) -> str:
    """Return a stable unique ID for a management-point entity."""
    return "_".join((gateway_id, embedded_id, *suffix))


class DaikinOnectaEntity(_DaikinOnectaCoordinatorEntity):
    """Base entity for a Daikin gateway device."""

    def __init__(
        self,
        coordinator: OnectaDataUpdateCoordinator,
        device: DaikinOnectaDevice,
    ) -> None:
        """Initialize the entity with its coordinator and gateway device."""
        super().__init__(coordinator)
        self._device_id = device.id

    @property
    def _device(self) -> DaikinOnectaDevice:
        """Return the gateway wrapper retained by the coordinator."""
        if (data := self.coordinator.data) is None:
            raise RuntimeError("Daikin coordinator has no device data")
        return data[self._device_id]

    def _raise_service_validation_error(self, translation_key: str) -> Never:
        """Raise a translated error for an unavailable device control."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"device": self._error_device_name},
        )

    def _raise_command_failed(self, translation_key: str) -> Never:
        """Raise a translated error when Daikin rejects a command."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"device": self._error_device_name},
        )

    @property
    def _error_device_name(self) -> str:
        """Return the device name used in translated error messages."""
        return self._device.name


class DaikinOnectaAccountEntity(_DaikinOnectaCoordinatorEntity):
    """Base entity backed by a Daikin Onecta account."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OnectaDataUpdateCoordinator) -> None:
        """Initialize shared account state."""
        super().__init__(coordinator)
        self._account_id = account_identifier(coordinator.config_entry)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, account_device_identifier(self._account_id))},
            manufacturer="Daikin",
            translation_key="account",
        )


class DaikinManagementPointEntity(DaikinOnectaEntity):
    """Base entity backed by a Daikin management point."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
    ) -> None:
        """Initialize shared coordinator and device state."""
        super().__init__(coordinator, device)
        self._embedded_id = embedded_id

    @property
    @override
    def _error_device_name(self) -> str:
        """Return the gateway and management-point name for error messages."""
        if self._device.ha_device_id is None:
            return self._device.name
        registry = dr.async_get(self.hass)
        identifier = (
            DOMAIN,
            management_point_unique_id(self._device_id, self._embedded_id),
        )
        management_point_device = registry.async_get_device_by_identifier(
            identifier, self.coordinator.config_entry.entry_id
        ) or registry.async_get_child_device_by_identifier(
            identifier, self.coordinator.config_entry.entry_id
        )
        if management_point_device is None:
            return self._device.name
        if management_point_device.name_by_user is not None:
            return management_point_device.name_by_user

        gateway_device = registry.async_get_device_by_identifier(
            (DOMAIN, self._device_id), self.coordinator.config_entry.entry_id
        )
        gateway_name = (
            gateway_device.name_by_user or gateway_device.name
            if gateway_device is not None
            else self._device.name
        )
        point = self._management_point
        point_name = (
            point.name.value
            if point is not None and point.name is not None and point.name.value
            else management_point_device.name
        )
        return f"{gateway_name} {point_name}"

    @property
    @override
    def available(self) -> bool:
        """Return whether the coordinator and gateway are available."""
        return super().available and self._device.available

    async def _async_execute_sub_client_command[SubClientT](
        self,
        sub_client_factory: Callable[[OnectaClient, str, str], SubClientT],
        command: Callable[[SubClientT], Awaitable[None]],
        translation_key: str,
    ) -> None:
        """Execute a command against a management-point sub-client."""
        await self._async_execute_command(
            lambda client: command(
                sub_client_factory(client, self._device_id, self._embedded_id)
            ),
            translation_key,
        )

    async def _async_execute_command(
        self,
        command: Callable[[OnectaClient], Awaitable[None]],
        translation_key: str,
    ) -> None:
        """Execute a cloud command or raise a translated Home Assistant error."""
        if not await self.coordinator.async_execute_command(command):
            self._raise_command_failed(translation_key)

    @callback
    def _publish_write_update(self) -> None:
        """Publish the locally updated model to every entity for the account."""
        self.coordinator.async_update_listeners()

    @property
    def _management_point(self) -> ManagementPoint | None:
        """Return the current source management point."""
        return self._device.management_point(self._embedded_id)

    def _characteristic(self, name: str) -> Characteristic | None:
        """Return a scalar characteristic from the current management point."""
        point = self._management_point
        return point.characteristic(name) if point is not None else None

    def _characteristic_exposed_on(self, name: str, platform: Platform) -> bool:
        """Return whether a scalar characteristic is still exposed on a platform."""
        point = self._management_point
        characteristic = self._characteristic(name)
        return (
            point is not None
            and characteristic is not None
            and scalar_platform_for_point(
                point,
                name,
                gateway_online=self._device.gateway_online,
            )
            is platform
        )

    @property
    @override
    def device_info(self) -> DeviceInfo | ChildDeviceInfo:
        """Return consistent device info for the source management point."""
        return management_point_device_info(self._device, self._embedded_id)
