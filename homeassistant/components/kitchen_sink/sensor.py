"""Demo platform that has a couple of fake sensors."""

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEGREE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .device import async_create_device


@dataclass(frozen=True, kw_only=True)
class DemoSensorEntityDescription(SensorEntityDescription):
    """Describes a demo sensor."""

    device_unique_id: str
    device_name: str
    state: StateType


OUTLET_SENSORS = (
    DemoSensorEntityDescription(
        key="outlet_1_power",
        device_unique_id="outlet_1",
        device_name="Outlet 1",
        state=50,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    DemoSensorEntityDescription(
        key="outlet_2_power",
        device_unique_id="outlet_2",
        device_name="Outlet 2",
        state=1500,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
)

STATISTICS_ISSUE_SENSORS = (
    DemoSensorEntityDescription(
        key="statistics_issue_1",
        name="Issue 1",
        device_unique_id="statistics_issues",
        device_name="Statistics issues",
        state=100,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    DemoSensorEntityDescription(
        key="statistics_issue_2",
        name="Issue 2",
        device_unique_id="statistics_issues",
        device_name="Statistics issues",
        state=100,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dogs",
    ),
    DemoSensorEntityDescription(
        key="statistics_issue_3",
        name="Issue 3",
        device_unique_id="statistics_issues",
        device_name="Statistics issues",
        state=100,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    DemoSensorEntityDescription(
        key="statistics_issue_5",
        name="Issue 5",
        device_unique_id="statistics_issues",
        device_name="Statistics issues",
        state=100,
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        native_unit_of_measurement=DEGREE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Everything but the Kitchen Sink config entry."""
    async_create_device(
        hass,
        config_entry.entry_id,
        None,
        "n_ch_power_strip",
        {"number_of_sockets": "2"},
        "2_ch_power_strip",
    )

    parent_device_id = dr.async_get_device_id_by_identifier(
        hass, (DOMAIN, "2_ch_power_strip"), config_entry_id=config_entry.entry_id
    )

    async_add_entities(
        [
            *(
                DemoSensor(description, parent_device_id=parent_device_id)
                for description in OUTLET_SENSORS
            ),
            *(DemoSensor(description) for description in STATISTICS_ISSUE_SENSORS),
        ]
    )

    for subentry_id, subentry in config_entry.subentries.items():
        if subentry.subentry_type != "entity":
            continue
        async_add_entities(
            [
                DemoSensor(
                    DemoSensorEntityDescription(
                        key=subentry_id,
                        name=None,
                        device_unique_id=subentry_id,
                        device_name=subentry.title,
                        state=subentry.data["state"],
                    )
                )
            ],
            config_subentry_id=subentry_id,
        )


class DemoSensor(SensorEntity):
    """Representation of a Demo sensor."""

    entity_description: DemoSensorEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_info: DeviceInfo | ChildDeviceInfo

    def __init__(
        self,
        description: DemoSensorEntityDescription,
        *,
        parent_device_id: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_native_value = description.state
        self._attr_unique_id = description.key

        if parent_device_id is not None:
            self._attr_device_info = ChildDeviceInfo(
                identifiers={(DOMAIN, description.device_unique_id)},
                name=description.device_name,
                parent_device_id=parent_device_id,
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, description.device_unique_id)},
                name=description.device_name,
            )
