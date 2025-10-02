"""LaMetric Update platform."""

from awesomeversion import AwesomeVersion

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LaMetricConfigEntry, LaMetricDataUpdateCoordinator
from .entity import LaMetricEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LaMetricConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LaMetric update platform."""

    coordinator = config_entry.runtime_data

    if coordinator.data.os_version >= AwesomeVersion("2.3.0"):
        async_add_entities([LaMetricUpdate(coordinator)])


class LaMetricUpdate(LaMetricEntity, UpdateEntity):
    """Representation of LaMetric Update."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(self, coordinator: LaMetricDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.data.serial_number}-update"

    @property
    def installed_version(self) -> str:
        """Return the installed version of the entity."""
        return self.coordinator.data.os_version

    @property
    def latest_version(self) -> str | None:
        """Return the latest version of the entity."""
        if not self.coordinator.data.update:
            return self.coordinator.data.os_version
        return self.coordinator.data.update.version
