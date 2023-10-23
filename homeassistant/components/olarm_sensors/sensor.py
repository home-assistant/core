"""Platform for binary sensor integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_FIRMWARE, CONF_OLARM_DEVICES, DOMAIN, LOGGER, VERSION
from .coordinator import OlarmCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Handle the setup of the platform."""
    entities = []
    for device in hass.data[DOMAIN]["devices"]:
        if device["deviceName"] not in entry.data[CONF_OLARM_DEVICES]:
            continue

        # Getting the instance of the DataCoordinator to update the data from Olarm.
        coordinator: OlarmCoordinator = hass.data[DOMAIN][device["deviceId"]]
        await coordinator.update_data()

        for panel in coordinator.panel_state:
            name = panel["name"] + " Trigger"
            sensor = OlarmTriggerSensor(
                area=panel["area_number"],
                area_name=name,
                coordinator=coordinator,
                hass=hass,
            )

            entities.append(sensor)

        LOGGER.info(
            "Adding Olarm Alarm Trigger Sensors for device (%s)",
            coordinator.olarm_device_name,
        )

    async_add_entities(entities)
    LOGGER.info("Added Olarm Alarm Trigger Sensors")


class OlarmTriggerSensor(SensorEntity):
    """Alarm Trigger Sensor."""

    area: int = 0
    area_name: str
    coordinator: OlarmCoordinator
    hass: HomeAssistant

    def __init__(
        self,
        area: int,
        area_name: str,
        coordinator: OlarmCoordinator,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the trigger sensor."""
        super().__init__()
        self.hass = hass
        self.area = area - 1
        self.area_name = area_name
        self.coordinator = coordinator

    @property
    def native_value(self) -> str | None:
        """Return the state of the trigger platforms."""
        self.coordinator: OlarmCoordinator = self.hass.data[DOMAIN][
            self.coordinator.olarm_device_id
        ]
        try:
            area_triggers = self.coordinator.area_triggers[self.area]
            if area_triggers and area_triggers != "":
                index = int(
                    str(area_triggers)
                    .split(" ", maxsplit=1)[0]
                    .split(",", maxsplit=1)[0]
                )
                return self.coordinator.sensor_data[index - 1]["name"]

            return area_triggers

        except (TypeError, IndexError):
            return None

    async def async_added_to_hass(self) -> None:
        """Write the state of the sensor to Home Assistant."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def unique_id(self) -> str:
        """The unique id for this entity sothat it can be managed from the ui."""
        return f"{self.coordinator.olarm_device_id}_area_trigger_{self.area}".replace(
            " ", "_"
        ).lower()

    @property
    def name(self) -> str:
        """The name of the zone from the Alarm Panel."""
        name = []
        name1 = self.area_name.replace("_", " ")
        for item in str(name1).lower().split(" "):
            name.append(str(item).capitalize())
        return " ".join(name) + " (" + self.coordinator.olarm_device_name + ") Triggers"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:alarm-bell"

    @property
    def should_poll(self) -> bool:
        """Disable polling. Integration will notify Home Assistant on sensor value update."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            manufacturer="Raine Pretorius",
            name=f"Olarm Sensors ({self.coordinator.olarm_device_name})",
            model=self.coordinator.olarm_device_make,
            identifiers={(DOMAIN, self.coordinator.olarm_device_id)},
            sw_version=VERSION,
            hw_version=self.coordinator.entry.data[CONF_DEVICE_FIRMWARE],
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.coordinator: OlarmCoordinator = self.hass.data[DOMAIN][
            self.coordinator.olarm_device_id
        ]
        self.async_write_ha_state()
