"""Component to allow numeric input for platforms."""
from pyvlx import PyVLX
from pyvlx.opening_device import Blind, DualRollerShutter, OpeningDevice

from homeassistant.components.number import (
    NumberExtraStoredData,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up cover(s) for Velux platform."""
    entities: list = []
    pyvlx: PyVLX = hass.data[DOMAIN][entry.entry_id]
    entities.append(VeluxHeartbeatInterval(pyvlx))
    for node in pyvlx.nodes:
        if isinstance(node, Blind):
            entities.append(VeluxOpenOrientation(node))
            entities.append(VeluxCloseOrientation(node))
        if isinstance(node, OpeningDevice) and not isinstance(node, DualRollerShutter):
            entities.append(VeluxDefaultVelocity(node))
    async_add_entities(entities)


class VeluxOpenOrientation(RestoreNumber):
    """Representation of a VeluxOpenOrientation number."""

    def __init__(self, node: Blind) -> None:
        """Initialize the number."""
        self.node: Blind = node
        self._number_option_unit_of_measurement = PERCENTAGE

    @property
    def device_info(self) -> DeviceInfo:
        """Return specific device attributes."""
        return {
            "identifiers": {(DOMAIN, str(self.node.node_id))},
            "name": self.node.name,
        }

    def set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = self.node.open_orientation_target = int(value)

    async def async_internal_added_to_hass(self) -> None:
        """Restore number from last number data."""
        await super().async_internal_added_to_hass()

        value: NumberExtraStoredData | None = await self.async_get_last_number_data()
        if value is not None and value.native_value is not None:
            try:
                self.set_native_value(value.native_value)
            except (TypeError, ValueError):
                self.set_native_value(50)

    @property
    def native_value(self) -> int:
        """Return the entity value to represent the entity state."""
        return self.node.open_orientation_target

    @property
    def native_max_value(self) -> int:
        """Return the max value."""
        return 100

    @property
    def native_min_value(self) -> int:
        """Return the min value."""
        return 0

    @property
    def native_step(self) -> float | None:
        """Return the native step value."""
        return 1.0

    @property
    def name(self) -> str:
        """Return the name of the number."""
        return self.node.name + "_open_orientation_target"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the number."""
        return str(self.node.node_id) + "_open_orientation_target"

    @property
    def entity_category(self) -> EntityCategory:
        """Return the entity_categor of the number."""
        return EntityCategory.CONFIG

    @property
    def mode(self) -> NumberMode:
        """Return the mode of the number."""
        return NumberMode.SLIDER


class VeluxCloseOrientation(RestoreNumber):
    """Representation of a VeluxCloseOrientation number."""

    def __init__(self, node: Blind) -> None:
        """Initialize the number."""
        self.node: Blind = node
        self._number_option_unit_of_measurement = PERCENTAGE

    @property
    def device_info(self) -> DeviceInfo:
        """Return specific device attributes."""
        return {
            "identifiers": {(DOMAIN, str(self.node.node_id))},
            "name": self.node.name,
        }

    def set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = self.node.close_orientation_target = int(value)

    async def async_internal_added_to_hass(self) -> None:
        """Restore number from last number data."""
        await super().async_internal_added_to_hass()

        value: NumberExtraStoredData | None = await self.async_get_last_number_data()
        if value is not None and value.native_value is not None:
            try:
                self.set_native_value(value.native_value)
            except (TypeError, ValueError):
                self.set_native_value(100)

    @property
    def native_value(self) -> float:
        """Return the entity value to represent the entity state."""
        return self.node.close_orientation_target

    @property
    def native_max_value(self) -> int:
        """Return the max value."""
        return 100

    @property
    def native_min_value(self) -> int:
        """Return the min value."""
        return 0

    @property
    def native_step(self) -> float | None:
        """Return the native step value."""
        return 1.0

    @property
    def name(self) -> str:
        """Return the name of the number."""
        return self.node.name + "_close_orientation_target"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the number."""
        return str(self.node.node_id) + "_close_orientation_target"

    @property
    def entity_category(self) -> EntityCategory:
        """Return the entity_category of the number."""
        return EntityCategory.CONFIG

    @property
    def mode(self) -> NumberMode:
        """Return the mode of the number."""
        return NumberMode.SLIDER


class VeluxDefaultVelocity(RestoreNumber):
    """Representation of a VeluxDefaultVelocity number."""

    def __init__(self, node: OpeningDevice) -> None:
        """Initialize the number."""
        self.node: OpeningDevice = node
        self._number_option_unit_of_measurement = PERCENTAGE

    @property
    def device_info(self) -> DeviceInfo:
        """Return specific device attributes."""
        return {
            "identifiers": {(DOMAIN, str(self.node.node_id))},
            "name": self.node.name,
        }

    def set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = (
            self._attr_native_value
        ) = self.node.default_velocity = int(value)  # type: ignore[assignment]

    async def async_added_to_hass(self) -> None:
        """Restore number from last number data."""
        await super().async_internal_added_to_hass()

        value: NumberExtraStoredData | None = await self.async_get_last_number_data()
        if value is not None and value.native_value is not None:
            try:
                self.set_native_value(value.native_value)
            except (TypeError, ValueError):
                self.set_native_value(100)

    @property
    def name(self) -> str:
        """Return the name of the Velux device."""
        return self.node.name + " Default Velocity"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this number."""
        return str(self.node.node_id) + "_default_velocity"

    @property
    def entity_category(self) -> EntityCategory:
        """Return the entity category of this number."""
        return EntityCategory.CONFIG

    @property
    def native_max_value(self) -> int:
        """Return the max value."""
        return 100

    @property
    def native_min_value(self) -> int:
        """Return the max value."""
        return 0

    @property
    def native_step(self) -> float | None:
        """Return the native step value."""
        return 1.0

    @property
    def mode(self) -> NumberMode:
        """Return the mode of this number."""
        return NumberMode.SLIDER


class VeluxHeartbeatInterval(RestoreNumber):
    """Representation of a VeluxHeartbeatInterval number."""

    def __init__(self, pyvlx: PyVLX) -> None:
        """Initialize the number entity."""
        self.pyvlx = pyvlx

    @property
    def device_info(self) -> DeviceInfo:
        """Return specific device attributes."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "connections": {("Host", self.pyvlx.config.host)},  # type: ignore[arg-type]
            "name": "KLF200 Gateway",
            "manufacturer": "Velux",
            "sw_version": self.pyvlx.version,
        }

    @property
    def name(self) -> str:
        """Return the name of the number."""
        return "Heartbeat interval (Default=30)"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the number."""
        return "velux_heartbeat_interval"

    @property
    def entity_category(self) -> EntityCategory:
        """Return the entity category of the number."""
        return EntityCategory.CONFIG

    def set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = self.pyvlx.heartbeat.interval = int(value)

    async def async_internal_added_to_hass(self) -> None:
        """Restore number from last number data."""
        await super().async_internal_added_to_hass()

        value: NumberExtraStoredData | None = await self.async_get_last_number_data()
        if value is not None and value.native_value is not None:
            try:
                self.set_native_value(value.native_value)
            except (TypeError, ValueError):
                self.set_native_value(30)

    @property
    def native_max_value(self) -> int:
        """Return the max value."""
        return 600

    @property
    def native_min_value(self) -> int:
        """Return the min value."""
        return 30

    @property
    def native_step(self) -> float | None:
        """Return the native step value."""
        return 10

    @property
    def mode(self) -> NumberMode:
        """Return the mode of the number."""
        return NumberMode.SLIDER
