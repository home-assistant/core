"""Provides a binary sensor for Home Connect."""

from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import HomeConnectDevice
from .const import (
    ATTR_VALUE,
    BSH_DOOR_STATE,
    BSH_DOOR_STATE_CLOSED,
    BSH_DOOR_STATE_LOCKED,
    BSH_DOOR_STATE_OPEN,
    BSH_REMOTE_CONTROL_ACTIVATION_STATE,
    BSH_REMOTE_START_ALLOWANCE_STATE,
    DOMAIN,
    REFRIGERATION_STATUS_DOOR_CHILLER,
    REFRIGERATION_STATUS_DOOR_CLOSED,
    REFRIGERATION_STATUS_DOOR_FREEZER,
    REFRIGERATION_STATUS_DOOR_OPEN,
    REFRIGERATION_STATUS_DOOR_REFRIGERATOR,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)
REFRIGERATION_DOOR_BOOLEAN_MAP = {
    REFRIGERATION_STATUS_DOOR_CLOSED: False,
    REFRIGERATION_STATUS_DOOR_OPEN: True,
}


@dataclass(frozen=True, kw_only=True)
class HomeConnectBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Entity Description class for binary sensors."""

    boolean_map: dict[str, bool] | None = None


BINARY_SENSORS = (
    HomeConnectBinarySensorEntityDescription(
        key=BSH_REMOTE_CONTROL_ACTIVATION_STATE,
        translation_key="remote_control",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=BSH_REMOTE_START_ALLOWANCE_STATE,
        translation_key="remote_start",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="BSH.Common.Status.LocalControlActive",
        translation_key="local_control",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="BSH.Common.Status.BatteryChargingState",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        boolean_map={
            "BSH.Common.EnumType.BatteryChargingState.Charging": True,
            "BSH.Common.EnumType.BatteryChargingState.Discharging": False,
        },
        translation_key="battery_charging_state",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="BSH.Common.Status.ChargingConnection",
        device_class=BinarySensorDeviceClass.PLUG,
        boolean_map={
            "BSH.Common.EnumType.ChargingConnection.Connected": True,
            "BSH.Common.EnumType.ChargingConnection.Disconnected": False,
        },
        translation_key="charging_connection",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="ConsumerProducts.CleaningRobot.Status.DustBoxInserted",
        translation_key="dust_box_inserted",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="ConsumerProducts.CleaningRobot.Status.Lifted",
        translation_key="lifted",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="ConsumerProducts.CleaningRobot.Status.Lost",
        translation_key="lost",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=REFRIGERATION_STATUS_DOOR_CHILLER,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="chiller_door",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=REFRIGERATION_STATUS_DOOR_FREEZER,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="freezer_door",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=REFRIGERATION_STATUS_DOOR_REFRIGERATOR,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="refrigerator_door",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect binary sensor."""

    def get_entities() -> list[BinarySensorEntity]:
        entities: list[BinarySensorEntity] = []
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        for device in hc_api.devices:
            entities.extend(
                HomeConnectBinarySensor(device, description)
                for description in BINARY_SENSORS
                if description.key in device.appliance.status
            )
            if BSH_DOOR_STATE in device.appliance.status:
                entities.append(HomeConnectDoorBinarySensor(device))
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectBinarySensor(HomeConnectEntity, BinarySensorEntity):
    """Binary sensor for Home Connect."""

    entity_description: HomeConnectBinarySensorEntityDescription

    @property
    def available(self) -> bool:
        """Return true if the binary sensor is available."""
        return self._attr_is_on is not None

    async def async_update(self) -> None:
        """Update the binary sensor's status."""
        if not self.device.appliance.status or not (
            status := self.device.appliance.status.get(self.bsh_key, {}).get(ATTR_VALUE)
        ):
            self._attr_is_on = None
            return
        if self.entity_description.boolean_map:
            self._attr_is_on = self.entity_description.boolean_map.get(status)
        elif status not in [True, False]:
            self._attr_is_on = None
        else:
            self._attr_is_on = status
        _LOGGER.debug("Updated, new state: %s", self._attr_is_on)


class HomeConnectDoorBinarySensor(HomeConnectBinarySensor):
    """Binary sensor for Home Connect Generic Door."""

    _attr_has_entity_name = False

    def __init__(
        self,
        device: HomeConnectDevice,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            device,
            HomeConnectBinarySensorEntityDescription(
                key=BSH_DOOR_STATE,
                device_class=BinarySensorDeviceClass.DOOR,
                boolean_map={
                    BSH_DOOR_STATE_CLOSED: False,
                    BSH_DOOR_STATE_LOCKED: False,
                    BSH_DOOR_STATE_OPEN: True,
                },
            ),
        )
        self._attr_unique_id = f"{device.appliance.haId}-Door"
        self._attr_name = f"{device.appliance.name} Door"
