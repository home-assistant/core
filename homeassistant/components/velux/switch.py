"""Component to interface with switches that can be controlled remotely."""
import logging
from typing import Any

from pyvlx import OnOffSwitch, OpeningDevice, PyVLX
from pyvlx.opening_device import DualRollerShutter

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .node_entity import VeluxNodeEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor(s) for Velux platform."""
    entities: list = []
    pyvlx: PyVLX = hass.data[DOMAIN][entry.entry_id]
    entities.append(VeluxHouseStatusMonitor(pyvlx))
    entities.append(VeluxHeartbeat(pyvlx))
    entities.append(VeluxHeartbeatLoadAllStates(pyvlx))
    for node in pyvlx.nodes:
        if isinstance(node, OnOffSwitch):
            _LOGGER.debug("Switch will be added: %s", node.name)
            entities.append(VeluxSwitch(node))
        if isinstance(node, OpeningDevice) and not isinstance(node, DualRollerShutter):
            entities.append(VeluxDefaultVelocityUsedSwitch(node))
    async_add_entities(entities)


class VeluxSwitch(VeluxNodeEntity, SwitchEntity):
    """Representation of a Velux physical switch."""

    def __init__(self, node: OnOffSwitch) -> None:
        """Initialize the switch."""
        self.node: OnOffSwitch = node
        super().__init__(node)

    @property
    def device_class(self) -> SwitchDeviceClass:
        """Return the device class of this node."""
        return SwitchDeviceClass.SWITCH

    @property
    def is_on(self) -> bool:
        """Return true if switch in on."""
        return self.node.is_on()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.node.set_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.node.set_off()


class VeluxDefaultVelocityUsedSwitch(SwitchEntity, RestoreEntity):
    """Representation of a Velux physical switch."""

    def __init__(self, node: OpeningDevice) -> None:
        """Initialize the cover."""
        self.node: OpeningDevice = node
        super().__init__()

    async def async_added_to_hass(self) -> None:
        """Restore state from last state."""
        await super().async_added_to_hass()
        s = await self.async_get_last_state()

        _LOGGER.info(f"restored numeric value for {self.name}: {str(s)}")  # noqa: G004

        if s is not None and s.state is not None and s.state == "on":
            self.turn_on()
        else:
            self.turn_off()

    @property
    def device_info(self) -> DeviceInfo:
        """Return specific device attributes."""
        return {
            "identifiers": {(DOMAIN, str(self.node.node_id))},
            "name": self.node.name,
        }

    @property
    def name(self) -> str:
        """Return the name of the Velux device."""
        return self.node.name + " Use Default Velocity"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this cover."""
        return str(self.node.node_id) + "_use_default_velocity"

    @property
    def entity_category(self) -> EntityCategory:
        """Return the entity category of this number."""
        return EntityCategory.CONFIG

    @property
    def device_class(self) -> SwitchDeviceClass:
        """Return the device class of this node."""
        return SwitchDeviceClass.SWITCH

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.node.use_default_velocity

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.node.use_default_velocity = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self.node.use_default_velocity = False


class VeluxHouseStatusMonitor(SwitchEntity):
    """Representation of a Velux HouseStatusMonitor switch."""

    def __init__(self, pyvlx: PyVLX) -> None:
        """Initialize the switch."""
        self.pyvlx: PyVLX = pyvlx

    @property
    def name(self) -> str:
        """Return name of the switch."""
        return "KLF200 House Status Monitor"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device attributes of the switch."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "connections": {("Host", self.pyvlx.config.host)},  # type: ignore[arg-type]
            "name": "KLF200 Gateway",
            "manufacturer": "Velux",
            "sw_version": self.pyvlx.version,
        }

    @property
    def entity_category(self) -> EntityCategory:
        """Return entity category of this switch."""
        return EntityCategory.CONFIG

    @property
    def device_class(self) -> SwitchDeviceClass:
        """Return device class of this switch."""
        return SwitchDeviceClass.SWITCH

    @property
    def unique_id(self) -> str:
        """Return unique ID of this switch."""
        return "KLF200_House_Status_Monitor"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.pyvlx.klf200.house_status_monitor_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.pyvlx.klf200.house_status_monitor_enable(pyvlx=self.pyvlx)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.pyvlx.klf200.house_status_monitor_disable(pyvlx=self.pyvlx)


class VeluxHeartbeat(SwitchEntity):
    """Representation of a Velux Heartbeat switch."""

    def __init__(self, pyvlx: PyVLX) -> None:
        """Initialize the cover."""
        self.pyvlx: PyVLX = pyvlx

    @property
    def name(self) -> str:
        """Name of the entity."""
        return "PyVLX Heartbeat"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device attributes of the switch."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "connections": {("Host", self.pyvlx.config.host)},  # type: ignore[arg-type]
            "name": "KLF200 Gateway",
            "manufacturer": "Velux",
            "sw_version": self.pyvlx.version,
        }

    @property
    def entity_category(self) -> EntityCategory:
        """Return the entity category of the switch."""
        return EntityCategory.CONFIG

    @property
    def device_class(self) -> SwitchDeviceClass:
        """Return device class of the switch."""
        return SwitchDeviceClass.SWITCH

    @property
    def unique_id(self) -> str:
        """Return unique ID of the switch."""
        return "PyVLX_Heartbeat"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return not self.pyvlx.heartbeat.stopped

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.pyvlx.heartbeat.start()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.pyvlx.heartbeat.stop()


class VeluxHeartbeatLoadAllStates(SwitchEntity):
    """Representation of a VeluxHeartbeatLoadAllStates switch."""

    def __init__(self, pyvlx: PyVLX) -> None:
        """Initialize the number entity."""
        self.pyvlx = pyvlx

    @property
    def name(self) -> str:
        """Name of the entity."""
        return "Load all states on Heartbeat"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device attributes of the switch."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "connections": {("Host", self.pyvlx.config.host)},  # type: ignore[arg-type]
            "name": "KLF200 Gateway",
            "manufacturer": "Velux",
            "sw_version": self.pyvlx.version,
        }

    @property
    def entity_category(self) -> EntityCategory:
        """Return the entity category of the switch."""
        return EntityCategory.CONFIG

    @property
    def device_class(self) -> SwitchDeviceClass:
        """Return device class of the switch."""
        return SwitchDeviceClass.SWITCH

    @property
    def unique_id(self) -> str:
        """Return unique ID of the switch."""
        return "Heartbeat_load_all_states"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.pyvlx.heartbeat.load_all_states

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.pyvlx.heartbeat.load_all_states = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.pyvlx.heartbeat.load_all_states = False
