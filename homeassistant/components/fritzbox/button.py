"""Support for AVM FRITZ!SmartHome templates."""
from pyfritzhome.devicetypes import FritzhomeTemplate

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzBoxEntity
from .common import get_coordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome template from ConfigEntry."""
    coordinator = get_coordinator(hass, entry.entry_id)

    @callback
    def _add_entities(templates: set[str] | None = None) -> None:
        """Add templates."""
        if templates is None:
            templates = coordinator.new_templates
        if not templates:
            return
        async_add_entities(FritzBoxTemplate(coordinator, ain) for ain in templates)

    entry.async_on_unload(coordinator.async_add_listener(_add_entities))

    _add_entities(set(coordinator.data.templates))


class FritzBoxTemplate(FritzBoxEntity, ButtonEntity):
    """Interface between FritzhomeTemplate and hass."""

    @property
    def data(self) -> FritzhomeTemplate:
        """Return the template data entity."""
        return self.coordinator.data.templates[self.ain]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return DeviceInfo(
            name=self.data.name,
            identifiers={(DOMAIN, self.ain)},
            configuration_url=self.coordinator.configuration_url,
            manufacturer="AVM",
            model="SmartHome Template",
        )

    async def async_press(self) -> None:
        """Apply template and refresh."""
        await self.hass.async_add_executor_job(self.apply_template)
        await self.coordinator.async_refresh()

    def apply_template(self) -> None:
        """Use Fritzhome to apply the template via ain."""
        self.coordinator.fritz.apply_template(self.ain)
