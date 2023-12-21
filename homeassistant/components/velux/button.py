"""Component to pressing a button as platforms."""

from pyvlx import PyVLX

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor(s) for Velux platform."""
    entities = []
    pyvlx: PyVLX = hass.data[DOMAIN][entry.entry_id]
    entities.append(VeluxGatewayRestart(pyvlx))
    async_add_entities(entities)


class VeluxGatewayRestart(ButtonEntity):
    """Representation of a KLF200 restart button entity."""

    def __init__(self, pyvlx: PyVLX) -> None:
        """Initialize the button entity."""
        self.pyvlx: PyVLX = pyvlx

    @property
    def name(self) -> str:
        """Name of the button entity."""
        return "KLF200 Reboot"

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
    def unique_id(self) -> str:
        """Return the unique ID."""
        return "KLF200_Reboot"

    @property
    def entity_category(self) -> EntityCategory:
        """Return the entity category."""
        return EntityCategory.CONFIG

    @property
    def device_class(self) -> ButtonDeviceClass:
        """Return the device class."""
        return ButtonDeviceClass.RESTART

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.pyvlx.klf200.reboot()
