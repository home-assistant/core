"""Support for System Bridge sensors."""
from datetime import timedelta

from systembridge import Bridge

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import BridgeDeviceEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up System Bridge sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    client: Bridge = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    async_add_entities(
        [
            BridgeOsSensor(coordinator, client),
        ],
        True,
    )


class BridgeSensor(BridgeDeviceEntity):
    """Defines a System Bridge sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        client: Bridge,
        key: str,
        name: str,
        icon: str,
        unit_of_measurement: str = "",
    ) -> None:
        """Initialize System Bridge sensor."""
        self._unit_of_measurement = unit_of_measurement

        super().__init__(coordinator, client, key, name, icon)

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class BridgeOsSensor(BridgeSensor):
    """Defines an OS sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, client: Bridge):
        """Initialize System Bridge sensor."""
        super().__init__(coordinator, client, "os", "Operating System", "mdi:devices")

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        bridge: Bridge = self.coordinator.data
        return f"{bridge.os.distro} {bridge.os.release}"
