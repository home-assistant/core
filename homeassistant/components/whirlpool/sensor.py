"""The Washer/Dryer Sensor for Whirlpool account."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
import time

from whirlpool.auth import Auth
from whirlpool.backendselector import BackendSelector
from whirlpool.washerdryer import WasherDryer

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import WhirlpoolData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ICON_D = "mdi:tumble-dryer"
ICON_W = "mdi:washing-machine"


@dataclass
class WhirlpoolSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable


@dataclass
class WhirlpoolSensorEntityDescription(
    SensorEntityDescription, WhirlpoolSensorEntityDescriptionMixin
):
    """Describes Whirlpool Washer sensor entity."""


SENSORS: tuple[WhirlpoolSensorEntityDescription, ...] = (
    WhirlpoolSensorEntityDescription(
        key="state",
        name="state",
        entity_registry_enabled_default=True,
        icon=ICON_W,
        has_entity_name=True,
        value_fn=lambda WasherDryer: WasherDryer.get_machine_state().name,
    ),
    WhirlpoolSensorEntityDescription(
        key="timeremaining",
        name="time remaining",
        # device_class=SensorDeviceClass.DURATION,
        # native_unit_of_measurement=TIME_SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
        icon=ICON_W,
        has_entity_name=True,
        value_fn=lambda WasherDryer: WasherDryer.get_attribute(
            "Cavity_TimeStatusEstTimeRemaining"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Config flow entry for Whrilpool Laundry."""
    whirlpool_data: WhirlpoolData = hass.data[DOMAIN][config_entry.entry_id]
    for appliance in whirlpool_data.appliances_manager.washer_dryers:
        entities = [
            WasherDryerClass(
                appliance["SAID"],
                appliance["NAME"],
                whirlpool_data.backend_selector,
                whirlpool_data.auth,
                description,
            )
            for description in SENSORS
        ]
        async_add_entities(entities)


class WasherDryerClass(SensorEntity):
    """A class for the whirlpool/maytag washer account."""

    _attr_should_poll = False

    def __init__(
        self,
        said: str,
        name: str,
        backend: BackendSelector,
        auth: Auth,
        description: WhirlpoolSensorEntityDescription,
    ) -> None:
        """Initialize the washer sensor."""
        self._name = name
        self._said = said

        self._wd: WasherDryer = WasherDryer(
            backend,
            auth,
            self._said,
            self.async_write_ha_state,
        )
        if self._name == "dryer":
            self._attr_icon = ICON_D
        self.entity_description: WhirlpoolSensorEntityDescription = description
        self._attr_unique_id = f"{said}-{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Device information for Whirlpool washer sensors."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._said)},
            name=self._name,
            manufacturer="Whirlpool",
            model="Washer",
        )

    async def async_added_to_hass(self) -> None:
        """Connect WasherDryer to the cloud."""
        await self._wd.connect()

    @property
    def native_value(self) -> StateType | str:
        """Return native value of sensor."""
        if self.entity_description.key == "timeremaining":
            value = int(self.entity_description.value_fn(self._wd))

            if value == 3540:
                value = 0
            washertime = time.gmtime(value)
            return time.strftime("%H:%M:%S", washertime)

        return self.entity_description.value_fn(self._wd)
