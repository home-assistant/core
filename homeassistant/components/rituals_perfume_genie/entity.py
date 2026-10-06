"""Base classes for Rituals Perfume Genie diffuser entities."""

from typing import override

from ritualsgenie import RitualsGenieHub, Sensor

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RitualsHubsCoordinator, RitualsSensorsCoordinator

MANUFACTURER = "Rituals Cosmetics"
MODEL = "The Perfume Genie"
MODEL2 = "The Perfume Genie 2.0"


def _device_info(hub: RitualsGenieHub) -> DeviceInfo:
    """Return the device info of a diffuser."""
    firmware = hub.firmware.current if hub.firmware else None

    return DeviceInfo(
        identifiers={(DOMAIN, hub.hublot)},
        manufacturer=MANUFACTURER,
        model=MODEL if hub.has_battery else MODEL2,
        name=hub.name,
        sw_version=str(firmware) if firmware else None,
    )


def _hub_available(hubs: RitualsHubsCoordinator, hublot: str) -> bool:
    """Return if a diffuser is on the account, and not reported offline."""
    if (hub := hubs.data.get(hublot)) is None:
        return False

    return hub.is_online is not False


class DiffuserEntity(CoordinatorEntity[RitualsHubsCoordinator]):
    """Representation of a diffuser entity, kept up to date with its state."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RitualsHubsCoordinator,
        hublot: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.hublot = hublot

        self._attr_unique_id = f"{hublot}-{description.key}"
        self._attr_device_info = _device_info(coordinator.data[hublot])

    @property
    def hub(self) -> RitualsGenieHub:
        """Return the diffuser."""
        return self.coordinator.data[self.hublot]

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and _hub_available(self.coordinator, self.hublot)


class DiffuserSensorsEntity(CoordinatorEntity[RitualsSensorsCoordinator]):
    """Representation of a diffuser entity, kept up to date with its sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RitualsSensorsCoordinator,
        description: EntityDescription,
        sensor: Sensor,
    ) -> None:
        """Initialize the entity."""
        # The context tells the coordinator which sensor this entity needs.
        super().__init__(coordinator, context=sensor)
        self.entity_description = description

        hub = coordinator.hubs.data[coordinator.hublot]
        self._attr_unique_id = f"{coordinator.hublot}-{description.key}"
        self._attr_device_info = _device_info(hub)

    @override
    async def async_added_to_hass(self) -> None:
        """Also listen to the diffusers, for a timely availability."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.hubs.async_add_listener(self._handle_coordinator_update)
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and _hub_available(self.coordinator.hubs, self.coordinator.hublot)
        )
