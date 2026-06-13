"""Support for Aqualink temperature sensors."""

from iaqualink.device import AqualinkBinarySensor, AqualinkDevice, AqualinkSwitch

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AqualinkConfigEntry
from .coordinator import AqualinkDataUpdateCoordinator
from .entity import AqualinkEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AqualinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up discovered binary sensors."""
    for coordinator in config_entry.runtime_data.coordinators.values():

        def _async_add_new_devices(
            devices: list[AqualinkDevice],
            _coordinator: AqualinkDataUpdateCoordinator = coordinator,
        ) -> None:
            async_add_entities(
                HassAqualinkBinarySensor(_coordinator, dev)
                for dev in devices
                if isinstance(dev, AqualinkBinarySensor)
                and not isinstance(dev, AqualinkSwitch)
            )

        coordinator.new_device_callbacks.append(_async_add_new_devices)
        _async_add_new_devices(list(coordinator.data.values()))


class HassAqualinkBinarySensor(
    AqualinkEntity[AqualinkBinarySensor], BinarySensorEntity
):
    """Representation of a binary sensor."""

    def __init__(
        self, coordinator: AqualinkDataUpdateCoordinator, dev: AqualinkBinarySensor
    ) -> None:
        """Initialize AquaLink binary sensor."""
        super().__init__(coordinator, dev)
        if dev.label == "Freeze Protection":
            self._attr_device_class = BinarySensorDeviceClass.COLD

    @property
    def is_on(self) -> bool:
        """Return whether the binary sensor is on or not."""
        return self.dev.is_on
