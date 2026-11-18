"""Base entities for the Daikin Onecta integration."""

from collections.abc import Awaitable, Callable, Iterable
from typing import Never, override

from daikin_onecta.client import OnectaClient

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import (
    ChildDeviceInfo,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANAGEMENT_POINT_DEVICE_TRANSLATION_KEYS
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice


def add_entities_on_coordinator_update(
    config_entry: DaikinOnectaConfigEntry,
    coordinator: OnectaDataUpdateCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    create_entities: Callable[[set[str]], Iterable[Entity]],
) -> None:
    """Add newly available entities whenever the cloud model changes."""
    added_unique_ids: set[str] = set()
    last_cloud_update_sequence: int | None = None

    @callback
    def add_new_entities() -> None:
        nonlocal last_cloud_update_sequence
        if last_cloud_update_sequence == coordinator.cloud_update_sequence:
            return
        last_cloud_update_sequence = coordinator.cloud_update_sequence
        entities = list(create_entities(added_unique_ids))
        if entities:
            for entity in entities:
                assert entity.unique_id is not None
                added_unique_ids.add(entity.unique_id)
            async_add_entities(entities)

    add_new_entities()
    config_entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


def _gateway_device_info(device: DaikinOnectaDevice) -> DeviceInfo:
    """Return the Home Assistant device info for a gateway."""
    return DeviceInfo(identifiers={(DOMAIN, device.id)})


def management_point_device_info(
    device: DaikinOnectaDevice, embedded_id: str
) -> DeviceInfo | ChildDeviceInfo:
    """Return consistent device info for a Daikin management point."""
    gateway = device.device
    management_point = device.management_point(embedded_id)
    if management_point is None:
        return _gateway_device_info(device)

    management_point_type = management_point.management_point_type
    if management_point_type == "gateway":
        return _gateway_device_info(device)

    if management_point_type == "climateControl":
        if len(gateway.management_points_by_type("climateControl")) <= 1:
            return _gateway_device_info(device)
        name = (
            management_point.name.value if management_point.name is not None else None
        )
        translation_key = None if name else "climate_zone"
        name = name or None
    else:
        translation_key = MANAGEMENT_POINT_DEVICE_TRANSLATION_KEYS.get(
            management_point_type, "management_point"
        )
        name = None

    assert device.ha_device_id is not None
    return ChildDeviceInfo(
        identifiers={(DOMAIN, f"{device.id}_{embedded_id}")},
        parent_device_id=device.ha_device_id,
        translation_key=translation_key,
        name=name,
    )


class DaikinOnectaEntity(CoordinatorEntity[OnectaDataUpdateCoordinator]):
    """Base entity for a Daikin gateway device."""

    def __init__(
        self,
        coordinator: OnectaDataUpdateCoordinator,
        device: DaikinOnectaDevice,
    ) -> None:
        """Initialize the entity with its coordinator and gateway device."""
        super().__init__(coordinator)
        self._device = device

    def _raise_service_validation_error(self, translation_key: str) -> Never:
        """Raise a translated error for an unavailable device control."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"device": self._device.name},
        )

    def _raise_command_failed(self, translation_key: str) -> Never:
        """Raise a translated error when Daikin rejects a command."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"device": self._device.name},
        )

    @property
    @override
    def device_info(self) -> DeviceInfo | ChildDeviceInfo:
        """Return the gateway device registry information."""
        return _gateway_device_info(self._device)


class DaikinOnectaAccountEntity(CoordinatorEntity[OnectaDataUpdateCoordinator]):
    """Base entity backed by a Daikin Onecta account."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OnectaDataUpdateCoordinator) -> None:
        """Initialize shared account state."""
        super().__init__(coordinator)
        self._account_id = (
            coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"account_{self._account_id}")},
            manufacturer="Daikin",
            name="Daikin Onecta account",
        )


class DaikinEntity(DaikinOnectaEntity):
    """Base entity backed by a Daikin gateway or management point."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str | None = None,
    ) -> None:
        """Initialize shared coordinator and device state."""
        super().__init__(coordinator, device)
        self._embedded_id = embedded_id

    @property
    @override
    def available(self) -> bool:
        """Return whether the coordinator, device, and point are available."""
        if not super().available or not self._device.available:
            return False
        return self._embedded_id is None or (
            self._device.management_point(self._embedded_id) is not None
        )

    async def _async_execute_command(
        self,
        command: Callable[[OnectaClient], Awaitable[None]],
        translation_key: str,
    ) -> None:
        """Execute a cloud command or raise a translated Home Assistant error."""
        if not await self.coordinator.async_execute_command(command):
            self._raise_command_failed(translation_key)


class DaikinManagementPointEntity(DaikinEntity):
    """Base entity backed by a Daikin management point."""

    _embedded_id: str

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
    ) -> None:
        """Initialize a management-point entity."""
        super().__init__(device, coordinator, embedded_id)

    @property
    @override
    def device_info(self) -> DeviceInfo | ChildDeviceInfo:
        """Return consistent device info for the source management point."""
        return management_point_device_info(self._device, self._embedded_id)
