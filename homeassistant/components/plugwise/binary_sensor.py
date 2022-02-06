"""Plugwise Binary Sensor component for Home Assistant."""
from plugwise.smile import Smile

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    COORDINATOR,
    DOMAIN,
    FLAME_ICON,
    FLOW_OFF_ICON,
    FLOW_ON_ICON,
    IDLE_ICON,
    LOGGER,
    NO_NOTIFICATION_ICON,
    NOTIFICATION_ICON,
)
from .entity import PlugwiseEntity

SEVERITIES = ["other", "info", "warning", "error"]
BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="dhw_state",
        name="DHW State",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="slave_boiler_state",
        name="Secondary Boiler State",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile binary_sensors from a config entry."""
    api: Smile = hass.data[DOMAIN][config_entry.entry_id]["api"]
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        COORDINATOR
    ]

    entities: list[BinarySensorEntity] = []
    is_thermostat = api.single_master_thermostat()

    all_devices = api.get_all_devices()
    for dev_id, device_properties in all_devices.items():

        if device_properties["class"] == "heater_central":
            data = api.get_device_data(dev_id)
            for description in BINARY_SENSORS:
                if description.key not in data:
                    continue

                entities.append(
                    PwBinarySensor(
                        api,
                        coordinator,
                        device_properties["name"],
                        dev_id,
                        description,
                    )
                )

        if device_properties["class"] == "gateway" and is_thermostat is not None:
            entities.append(
                PwNotifySensor(
                    api,
                    coordinator,
                    device_properties["name"],
                    dev_id,
                    BinarySensorEntityDescription(
                        key="plugwise_notification",
                        name="Plugwise Notification",
                    ),
                )
            )

    async_add_entities(entities, True)


class SmileBinarySensor(PlugwiseEntity, BinarySensorEntity):
    """Represent Smile Binary Sensors."""

    def __init__(
        self,
        api: Smile,
        coordinator: DataUpdateCoordinator,
        name: str,
        dev_id: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialise the binary_sensor."""
        super().__init__(api, coordinator, name, dev_id)
        self.entity_description = description
        self._attr_is_on = False
        self._attr_unique_id = f"{dev_id}-{description.key}"

        if dev_id == self._api.heater_id:
            self._entity_name = "Auxiliary"

        self._name = f"{self._entity_name} {description.name}"

        if dev_id == self._api.gateway_id:
            self._entity_name = f"Smile {self._entity_name}"

    @callback
    def _async_process_data(self) -> None:
        """Update the entity."""
        raise NotImplementedError


class PwBinarySensor(SmileBinarySensor):
    """Representation of a Plugwise binary_sensor."""

    @callback
    def _async_process_data(self) -> None:
        """Update the entity."""
        if not (data := self._api.get_device_data(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._dev_id)
            self.async_write_ha_state()
            return

        if self.entity_description.key not in data:
            self.async_write_ha_state()
            return

        self._attr_is_on = data[self.entity_description.key]

        if self.entity_description.key == "dhw_state":
            self._attr_icon = FLOW_ON_ICON if self._attr_is_on else FLOW_OFF_ICON
        if self.entity_description.key == "slave_boiler_state":
            self._attr_icon = FLAME_ICON if self._attr_is_on else IDLE_ICON

        self.async_write_ha_state()


class PwNotifySensor(SmileBinarySensor):
    """Representation of a Plugwise Notification binary_sensor."""

    def __init__(
        self,
        api: Smile,
        coordinator: DataUpdateCoordinator,
        name: str,
        dev_id: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id, description)

        self._attr_extra_state_attributes = {}

    @callback
    def _async_process_data(self) -> None:
        """Update the entity."""
        notify = self._api.notifications

        for severity in SEVERITIES:
            self._attr_extra_state_attributes[f"{severity}_msg"] = []

        self._attr_is_on = False
        self._attr_icon = NO_NOTIFICATION_ICON

        if notify:
            self._attr_is_on = True
            self._attr_icon = NOTIFICATION_ICON

            for details in notify.values():
                for msg_type, msg in details.items():
                    if msg_type not in SEVERITIES:
                        msg_type = "other"

                    self._attr_extra_state_attributes[f"{msg_type.lower()}_msg"].append(
                        msg
                    )

        self.async_write_ha_state()
