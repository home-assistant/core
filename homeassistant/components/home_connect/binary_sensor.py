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
from .entity import HomeConnectEntity, HomeConnectEntityDescription

_LOGGER = logging.getLogger(__name__)
REFRIGERATION_DOOR_BOOLEAN_MAP = {
    REFRIGERATION_STATUS_DOOR_CLOSED: False,
    REFRIGERATION_STATUS_DOOR_OPEN: True,
}


@dataclass(frozen=True, kw_only=True)
class HomeConnectBinarySensorEntityDescription(
    BinarySensorEntityDescription, HomeConnectEntityDescription
):
    """Entity Description class for binary sensors."""

    boolean_map: dict[str, bool] | None = None


BINARY_SENSORS = (
    HomeConnectBinarySensorEntityDescription(
        key=BSH_REMOTE_CONTROL_ACTIVATION_STATE,
        desc="Remote control",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=BSH_REMOTE_START_ALLOWANCE_STATE,
        desc="Remote start",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="BSH.Common.Status.LocalControlActive",
        desc="Local control",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="BSH.Common.Status.BatteryChargingState",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        boolean_map={
            "BSH.Common.EnumType.BatteryChargingState.Charging": True,
            "BSH.Common.EnumType.BatteryChargingState.Discharging": False,
        },
        desc="Battery charging",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="BSH.Common.Status.ChargingConnection",
        device_class=BinarySensorDeviceClass.PLUG,
        boolean_map={
            "BSH.Common.EnumType.ChargingConnection.Connected": True,
            "BSH.Common.EnumType.ChargingConnection.Disconnected": False,
        },
        desc="Charging connection",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="ConsumerProducts.CleaningRobot.Status.DustBoxInserted",
        desc="Dust box inserted",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="ConsumerProducts.CleaningRobot.Status.Lifted",
        desc="Lifted",
    ),
    HomeConnectBinarySensorEntityDescription(
        key="ConsumerProducts.CleaningRobot.Status.Lost",
        desc="Lost",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=REFRIGERATION_STATUS_DOOR_CHILLER,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        desc="Chiller door",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=REFRIGERATION_STATUS_DOOR_FREEZER,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        desc="Freezer door",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=REFRIGERATION_STATUS_DOOR_REFRIGERATOR,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        desc="Refrigerator door",
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
                desc="Door",
            ),
        )
        self._attr_unique_id = f"{device.appliance.haId}-Door"
