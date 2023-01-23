"""Sensor for myUplink."""
from myuplink.models import DevicePoint

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyUplinkDataCoordinator
from .const import (
    DOMAIN,
    MU_DATAGROUP_DEVICES,
    MU_DATAGROUP_POINTS,
    MU_DEVICE_CONNECTIONSTATE,
    MU_DEVICE_FIRMWARE_CURRENT,
    MU_DEVICE_FIRMWARE_DESIRED,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the myUplink sensor."""

    entities: list[MyUplinkSensor] = []

    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: MyUplinkDataCoordinator = data["coordinator"]

    # Setup device sensors
    mu_devices = coordinator.data[MU_DATAGROUP_DEVICES]

    for device_id in mu_devices:
        entities.append(
            MyUplinkSensor(
                coordinator=coordinator,
                data_group=MU_DATAGROUP_DEVICES,
                data_id=MU_DEVICE_FIRMWARE_CURRENT,
                device_id=device_id,
                name="Firmware Current",
                u_id="firmware_current",
                diag=True,
            )
        )
        entities.append(
            MyUplinkSensor(
                coordinator=coordinator,
                data_group=MU_DATAGROUP_DEVICES,
                data_id=MU_DEVICE_FIRMWARE_DESIRED,
                device_id=device_id,
                name="Firmware Desired",
                u_id="firmware_desired",
                diag=True,
            )
        )
        entities.append(
            MyUplinkSensor(
                coordinator=coordinator,
                data_group=MU_DATAGROUP_DEVICES,
                data_id=MU_DEVICE_CONNECTIONSTATE,
                device_id=device_id,
                name="Connection State",
                u_id="connectionstate",
                diag=True,
            )
        )

    # Setup device point sensors
    mu_device_points = coordinator.data[MU_DATAGROUP_POINTS]
    for device_id in mu_device_points:
        for point_id in coordinator.data[MU_DATAGROUP_POINTS][device_id]:
            point_data: DevicePoint = coordinator.data[MU_DATAGROUP_POINTS][device_id][
                point_id
            ]
            entities.append(
                MyUplinkSensor(
                    coordinator=coordinator,
                    data_group=MU_DATAGROUP_POINTS,
                    data_id=point_id,
                    device_id=device_id,
                    name=point_data.parameter_name,
                    u_id=point_id,
                    diag=False,
                )
            )

    async_add_entities(entities)


class MyUplinkSensor(SensorEntity):
    """Representation of a sensor."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        data_group,
        data_id,
        device_id,
        name: str,
        u_id: str,
        diag: bool,
    ) -> None:
        """Initialize the sensor."""

        self._attr_should_poll = False

        # Internal properties
        self.mu_device_id = device_id
        self.mu_data_group = data_group
        self.mu_data_id = data_id

        # Coordinator setup
        self.coordinator = coordinator
        self.coordinator.async_add_listener(self.async_update_state)

        # Basic values
        self._attr_has_entity_name = True
        self._attr_name = name
        self._attr_unique_id = f"{device_id}-{u_id}"
        self._attr_device_info = {"identifiers": {(DOMAIN, device_id)}}

        # Set unit of measurement and device class for device points
        if self.mu_data_group == MU_DATAGROUP_POINTS:
            device_point: DevicePoint = self.coordinator.data[self.mu_data_group][
                self.mu_device_id
            ][self.mu_data_id]

            self._attr_native_unit_of_measurement = device_point.parameter_unit

            if device_point.parameter_unit == "°C":
                self._attr_device_class = SensorDeviceClass.TEMPERATURE

        # Is this DIAGNOSTIC sensor?
        if diag:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Sensor state value."""
        data_value = self.coordinator.data[self.mu_data_group][self.mu_device_id][
            self.mu_data_id
        ]

        # Get state value from device point model
        if self.mu_data_group == MU_DATAGROUP_POINTS:
            device_point: DevicePoint = data_value
            return device_point.value

        return data_value

    def async_update_state(self) -> None:
        """Update state on sensor."""
        self.schedule_update_ha_state()
