"""Demo platform that has a couple of fake sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, StateType, UndefinedType

from . import DOMAIN
from .device import async_create_device


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    # pylint: disable-next=hass-argument-type
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

    async_add_entities(
        [
            DemoSensor(
                device_unique_id="outlet_1",
                unique_id="outlet_1_power",
                device_name="Outlet 1",
                entity_name=UNDEFINED,
                state=50,
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT,
                unit_of_measurement=UnitOfPower.WATT,
                via_device="2_ch_power_strip",
            ),
            DemoSensor(
                device_unique_id="outlet_2",
                unique_id="outlet_2_power",
                device_name="Outlet 2",
                entity_name=UNDEFINED,
                state=1500,
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT,
                unit_of_measurement=UnitOfPower.WATT,
                via_device="2_ch_power_strip",
            ),
            DemoSensor(
                device_unique_id="statistics_issues",
                unique_id="statistics_issue_1",
                device_name="Statistics issues",
                entity_name="Issue 1",
                state=100,
                device_class=None,
                state_class=SensorStateClass.MEASUREMENT,
                unit_of_measurement=UnitOfPower.WATT,
            ),
            DemoSensor(
                device_unique_id="statistics_issues",
                unique_id="statistics_issue_2",
                device_name="Statistics issues",
                entity_name="Issue 2",
                state=100,
                device_class=None,
                state_class=SensorStateClass.MEASUREMENT,
                unit_of_measurement="dogs",
            ),
            DemoSensor(
                device_unique_id="statistics_issues",
                unique_id="statistics_issue_3",
                device_name="Statistics issues",
                entity_name="Issue 3",
                state=100,
                device_class=None,
                state_class=None,
                unit_of_measurement=UnitOfPower.WATT,
            ),
        ]
    )

    for subentry_id, subentry in config_entry.subentries.items():
        async_add_entities(
            [
                DemoSensor(
                    device_unique_id=subentry_id,
                    unique_id=subentry_id,
                    device_name=subentry.title,
                    entity_name=None,
                    state=subentry.data["state"],
                    device_class=None,
                    state_class=None,
                    unit_of_measurement=None,
                )
            ],
            subentry_id=subentry_id,
        )


class DemoSensor(SensorEntity):
    """Representation of a Demo sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        *,
        device_unique_id: str,
        unique_id: str,
        device_name: str,
        entity_name: str | None | UndefinedType,
        state: StateType,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        unit_of_measurement: str | None,
        via_device: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        self._attr_device_class = device_class
        if entity_name is not UNDEFINED:
            self._attr_name = entity_name
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_native_value = state
        self._attr_state_class = state_class
        self._attr_unique_id = unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_unique_id)},
            name=device_name,
        )
        if via_device:
            self._attr_device_info["via_device"] = (DOMAIN, via_device)
