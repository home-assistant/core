"""Support for Netgear LTE sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import ModemData
from .const import DOMAIN
from .entity import LTEEntity


@dataclass(frozen=True, kw_only=True)
class NetgearLTESensorEntityDescription(SensorEntityDescription):
    """Class describing Netgear LTE entities."""

    value_fn: Callable[[ModemData], StateType] | None = None


SENSORS: tuple[NetgearLTESensorEntityDescription, ...] = (
    NetgearLTESensorEntityDescription(
        key="sms",
        native_unit_of_measurement="unread",
        value_fn=lambda modem_data: sum(1 for x in modem_data.data.sms if x.unread),
    ),
    NetgearLTESensorEntityDescription(
        key="sms_total",
        native_unit_of_measurement="messages",
        value_fn=lambda modem_data: len(modem_data.data.sms),
    ),
    NetgearLTESensorEntityDescription(
        key="usage",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        value_fn=lambda modem_data: round(modem_data.data.usage / 1024**2, 1),
    ),
    NetgearLTESensorEntityDescription(
        key="radio_quality",
        native_unit_of_measurement=PERCENTAGE,
    ),
    NetgearLTESensorEntityDescription(
        key="rx_level",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ),
    NetgearLTESensorEntityDescription(
        key="tx_level",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ),
    NetgearLTESensorEntityDescription(key="upstream"),
    NetgearLTESensorEntityDescription(key="connection_text"),
    NetgearLTESensorEntityDescription(key="connection_type"),
    NetgearLTESensorEntityDescription(key="current_ps_service_type"),
    NetgearLTESensorEntityDescription(key="register_network_display"),
    NetgearLTESensorEntityDescription(key="current_band"),
    NetgearLTESensorEntityDescription(key="cell_id"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netgear LTE sensor."""
    modem_data = hass.data[DOMAIN].get_modem_data(entry.data)

    async_add_entities(
        NetgearLTESensor(entry, modem_data, sensor) for sensor in SENSORS
    )


class NetgearLTESensor(LTEEntity, SensorEntity):
    """Base LTE sensor entity."""

    entity_description: NetgearLTESensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(self.modem_data)
        return getattr(self.modem_data.data, self.entity_description.key)
