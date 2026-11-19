"""Base entities for the Daikin Onecta integration."""

from collections.abc import Awaitable, Callable, Iterable, Iterator
from typing import Never, override

from daikin_onecta.client import OnectaClient
from daikin_onecta.models import ManagementPoint

from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
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

EntityIdChecker = Callable[[Platform, str], bool]


class _DaikinOnectaCoordinatorEntity(CoordinatorEntity[OnectaDataUpdateCoordinator]):
    """Share coordinator state updates and successful-add lifecycle handling."""

    _on_entity_added: CALLBACK_TYPE | None = None
    _on_entity_removed: CALLBACK_TYPE | None = None

    def set_unique_id_callbacks(
        self, on_added: CALLBACK_TYPE, on_removed: CALLBACK_TYPE
    ) -> None:
        """Set callbacks for tracking an entity after it is added to Home Assistant."""
        self._on_entity_added = on_added
        self._on_entity_removed = on_removed

    @override
    async def async_added_to_hass(self) -> None:
        """Release unique IDs only after this entity was actually added."""
        await super().async_added_to_hass()
        if (on_added := self._on_entity_added) is not None:
            on_added()
            if on_removed := self._on_entity_removed:
                self.async_on_remove(on_removed)
            self._on_entity_added = None
            self._on_entity_removed = None

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

                def add_unique_id(unique_id: str = unique_id) -> None:
                    added_unique_ids.add(unique_id)

                def remove_unique_id(unique_id: str = unique_id) -> None:
                    added_unique_ids.discard(unique_id)

                if isinstance(entity, _DaikinOnectaCoordinatorEntity):
                    entity.set_unique_id_callbacks(add_unique_id, remove_unique_id)
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


def _gateway_device_info(device: DaikinOnectaDevice) -> DeviceInfo:
    """Return the Home Assistant device info for a gateway."""
    return DeviceInfo(identifiers={(DOMAIN, device.id)})


def management_point_unique_id(gateway_id: str, embedded_id: str, *suffix: str) -> str:
    """Return a stable unique ID for a management-point entity."""
    return "_".join((gateway_id, embedded_id, *suffix))


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

    if device.ha_device_id is None:
        return _gateway_device_info(device)
    return ChildDeviceInfo(
        identifiers={(DOMAIN, management_point_unique_id(device.id, embedded_id))},
        parent_device_id=device.ha_device_id,
        translation_key=translation_key,
        name=name,
    )


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
        self._initial_device = device

    @property
    def _device(self) -> DaikinOnectaDevice:
        """Return the current gateway wrapper, which may be replaced on reappearance."""
        data = self.coordinator.data
        if isinstance(data, dict) and (device := data.get(self._device_id)) is not None:
            return device
        return self._initial_device

    @property
    def device_present_in_cloud(self) -> bool:
        """Return whether the entity's gateway is present in the latest response."""
        return self._device.present_in_cloud

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


class DaikinOnectaAccountEntity(_DaikinOnectaCoordinatorEntity):
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
        device = self._device
        if not super().available or not device.available:
            return False
        return self._embedded_id is None or (
            device.management_point(self._embedded_id) is not None
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
    def _management_point(self) -> ManagementPoint | None:
        """Return the current source management point."""
        return self._device.management_point(self._embedded_id)

    @property
    @override
    def device_info(self) -> DeviceInfo | ChildDeviceInfo:
        """Return consistent device info for the source management point."""
        return management_point_device_info(self._device, self._embedded_id)
