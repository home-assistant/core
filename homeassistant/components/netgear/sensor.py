"""Support for Netgear routers."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_MEGABYTES, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, KEY_COORDINATOR, KEY_ROUTER
from .router import NetgearDeviceEntity, NetgearRouter, NetgearRouterEntity

SENSOR_TYPES = {
    "type": SensorEntityDescription(
        key="type",
        name="link type",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:lan",
    ),
    "link_rate": SensorEntityDescription(
        key="link_rate",
        name="link rate",
        native_unit_of_measurement="Mbps",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:speedometer",
    ),
    "signal": SensorEntityDescription(
        key="signal",
        name="signal strength",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "ssid": SensorEntityDescription(
        key="ssid",
        name="ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:wifi-marker",
    ),
    "conn_ap_mac": SensorEntityDescription(
        key="conn_ap_mac",
        name="access point mac",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:router-network",
    ),
}

SENSOR_TRAFFIC_TYPES = [
    SensorEntityDescription(
        key="NewTodayUpload",
        name="Upload today",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="NewTodayDownload",
        name="Download today",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="NewYesterdayUpload",
        name="Upload yesterday",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="NewYesterdayDownload",
        name="Download yesterday",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="NewWeekUpload",
        name="Upload week",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="NewWeekDownload",
        name="Download week",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="NewMonthUpload",
        name="Upload month",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="NewMonthDownload",
        name="Download month",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="NewLastMonthUpload",
        name="Upload last month",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="NewLastMonthDownload",
        name="Download last month",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for Netgear component."""
    router = hass.data[DOMAIN][entry.entry_id][KEY_ROUTER]
    coordinator = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR]

    # Router entities
    router_entities = []

    for entity_des in SENSOR_TRAFFIC_TYPES:
        router_entities.append(
            NetgearRouterTrafficEntity(coordinator, router, entity_des)
        )

    async_add_entities(router_entities)

    # Entities per network device
    tracked = set()
    sensors = ["type", "link_rate", "signal"]
    if router.method_version == 2:
        sensors.extend(["ssid", "conn_ap_mac"])

    @callback
    def new_device_callback() -> None:
        """Add new devices if needed."""
        if not coordinator.data:
            return

        new_entities = []

        for mac, device in router.devices.items():
            if mac in tracked:
                continue

            new_entities.extend(
                [
                    NetgearSensorEntity(coordinator, router, device, attribute)
                    for attribute in sensors
                ]
            )
            tracked.add(mac)

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(new_device_callback))

    coordinator.data = True
    new_device_callback()


class NetgearSensorEntity(NetgearDeviceEntity, SensorEntity):
    """Representation of a device connected to a Netgear router."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: NetgearRouter,
        device: dict,
        attribute: str,
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(coordinator, router, device)
        self._attribute = attribute
        self.entity_description = SENSOR_TYPES[self._attribute]
        self._name = f"{self.get_device_name()} {self.entity_description.name}"
        self._unique_id = f"{self._mac}-{self._attribute}"
        self._state = self._device.get(self._attribute)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""
        self._device = self._router.devices[self._mac]
        self._active = self._device["active"]
        if self._device.get(self._attribute) is not None:
            self._state = self._device[self._attribute]


class NetgearRouterTrafficEntity(NetgearRouterEntity, SensorEntity):
    """Representation of a device connected to a Netgear router."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: NetgearRouter,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(coordinator, router)
        self.entity_description = entity_description
        self._name = f"{router.device_name} {self.entity_description.name}"
        self._unique_id = f"{router.serial_number}-{self.entity_description.key}"
        self._traffic = None
        self._traffic_avg = None
        self._traffic_avg_attr = f"{self.entity_description.name} average"
        self.async_update_device()

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._traffic

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        extra_attr = {}
        if self._traffic_avg is not None:
            extra_attr[self._traffic_avg_attr] = self._traffic_avg
        return extra_attr

    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""
        if self._router.traffic_data is not None:
            data = self._router.traffic_data.get(self.entity_description.key)
            if isinstance(data, float):
                self._traffic = data
            elif isinstance(data, tuple):
                self._traffic = data[0]
                self._traffic_avg = data[1]

    async def async_added_to_hass(self):
        """Entity added to hass."""
        self._router.traffic_meter_entities = self._router.traffic_meter_entities + 1
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self):
        """Entity removed from hass."""
        self._router.traffic_meter_entities = self._router.traffic_meter_entities - 1
        await super().async_will_remove_from_hass()
