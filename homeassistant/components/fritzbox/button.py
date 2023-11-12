"""Support for AVM FRITZ!SmartHome templates."""
from pyfritzhome.devicetypes import FritzhomeTemplate

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzboxDataUpdateCoordinator, FritzBoxEntity
from .const import CONF_COORDINATOR, CONF_EVENT_LISTENER, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome template from ConfigEntry."""
    coordinator: FritzboxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        CONF_COORDINATOR
    ]

    def _add_new_templates(event: Event) -> None:
        """Add newly discovered template."""
        async_add_entities(
            [FritzBoxTemplate(coordinator, ain) for ain in event.data.get("ains", [])]
        )

    hass.data[DOMAIN][entry.entry_id][CONF_EVENT_LISTENER].append(
        hass.bus.async_listen(
            f"{DOMAIN}_{entry.entry_id}_new_templates", _add_new_templates
        )
    )

    async_add_entities(
        [FritzBoxTemplate(coordinator, ain) for ain in coordinator.data.templates]
    )


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
