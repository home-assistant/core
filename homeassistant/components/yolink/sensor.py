"""YoLink Binary Sensor."""
from __future__ import annotations

from yolink.client import YoLinkClient

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_STATE, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import percentage

from .const import (
    ATTR_CLIENT,
    ATTR_DEVICE,
    ATTR_DEVICE_DOOR_SENSOR,
    ATTR_DEVICE_TYPE,
    ATTR_MQTT_CLIENT,
    ATTR_PLATFORM_SENSOR,
    DOMAIN,
)
from .entity import YoLinkEntity

SENSOR_DESC_MAP: dict[str, SensorEntityDescription] = {
    "battery": SensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        name="Battery",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

SENSOR_DEVICE_TYPE = [ATTR_DEVICE_DOOR_SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink Sensor from a config entry."""
    sensor_devices = [
        device
        for device in hass.data[DOMAIN][config_entry.entry_id][ATTR_DEVICE]
        if device[ATTR_DEVICE_TYPE] in SENSOR_DEVICE_TYPE
    ]
    yl_client = hass.data[DOMAIN][config_entry.entry_id][ATTR_CLIENT]
    yl_mqtt_client = hass.data[DOMAIN][config_entry.entry_id][ATTR_MQTT_CLIENT]
    entities = []
    for sensor_device in sensor_devices:
        sensor_entities = get_sensor_entities(hass, sensor_device, yl_client)
        if sensor_entities is not None:
            for entity in sensor_entities:
                entities.append(entity)
    yl_mqtt_client.add_device_subscription(ATTR_PLATFORM_SENSOR, entities)
    async_add_entities(entities)


def get_sensor_entities(
    hass: HomeAssistant, device: dict, client: YoLinkClient
) -> list[YoLinkEntity] | None:
    """Get device entities."""
    if device[ATTR_DEVICE_TYPE] == ATTR_DEVICE_DOOR_SENSOR:
        return [YoLinkSensorBatteryEntity(hass, device, client)]
    return None


class YoLinkSensorBatteryEntity(YoLinkEntity, SensorEntity):
    """YoLink Sensor Entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: dict,
        client: YoLinkClient,
    ) -> None:
        """Init YoLink Sensor."""
        super().__init__(hass, device, client)
        self.entity_description = SENSOR_DESC_MAP["battery"]
        self._attr_unique_id = f"{device['deviceId']} {self.entity_description.key}"
        self._attr_name = f"{device['name']} ({self.entity_description.name})"

    async def async_added_to_hass(self) -> None:
        """Add to hass."""

        async def request_state():
            resp = await self.fetch_state_with_api()
            if "state" in resp.data:
                await self.update_entity_state(resp.data[CONF_STATE])

        self.hass.create_task(request_state())

    async def update_entity_state(self, state: dict) -> None:
        """Update HA Entity State."""
        if state is None:
            return
        self._attr_native_value = percentage.ordered_list_item_to_percentage(
            [1, 2, 3, 4], state["battery"]
        )
        await self.async_update_ha_state()
