"""Sensor platform for JVC Projector integration."""

from __future__ import annotations

from jvcprojector import const

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JvcProjectorDataUpdateCoordinator
from .const import DOMAIN
from .entity import JvcProjectorEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator: JvcProjectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        JvcSensor(
            coordinator,
            "power",
            SensorEntityDescription(
                key="power",
                name="Power",
                device_class=SensorDeviceClass.ENUM,
                icon="mdi:power",
                options=[
                    const.OFF,
                    const.STANDBY,
                    const.ON,
                    const.WARMING,
                    const.COOLING,
                    const.ERROR,
                ],
            ),
        ),
        JvcSensor(
            coordinator,
            "input",
            SensorEntityDescription(
                key="input",
                name="Input",
                device_class=SensorDeviceClass.ENUM,
                icon="mdi:video-input-hdmi",
                options=[
                    const.INPUT_HDMI1,
                    const.INPUT_HDMI2,
                    const.NOSIGNAL,
                ],
            ),
        ),
    ]
    async_add_entities(sensors)


class JvcSensor(JvcProjectorEntity, SensorEntity):
    """The entity class for JVC Projector integration."""

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
        entity_type: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the JVC Projector sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self.entity_description = description
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        self._attr_unique_id = f"{self._coordinator.device.mac}_{entity_type}"

        self._attributes: dict[str, str] = {}

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes of the sensor."""
        return self._attributes

    def update_callback(self) -> None:
        """Schedule a state update."""
        self.async_schedule_update_ha_state(True)

    @property
    def native_value(self) -> str | None:
        """Return the native value."""
        if self.entity_description.key == "power":
            return self.coordinator.data["power"]
        if self.entity_description.key == "input":
            return self.coordinator.data["input"]
        return None
