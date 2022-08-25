"""The Washer/Dryer Sensor for Whirlpool account."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
import time

from whirlpool.auth import Auth
from whirlpool.backendselector import BackendSelector
from whirlpool.washerdryer import WasherDryer

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TIME_SECONDS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WhirlpoolData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BASE_INTERVAL = timedelta(minutes=5)
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
        key="washer",
        name="washer state",
        entity_registry_enabled_default=True,
        has_entity_name=True,
        value_fn=WasherDryer.get_machine_state,
    ),
    WhirlpoolSensorEntityDescription(
        key="timeremaining",
        name="washer time remaining",
        device_class=SensorDeviceClass.TIMESTAMP,
        native_unit_of_measurement=TIME_SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
        has_entity_name=True,
        value_fn=WasherDryer.get_attribute,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Config flow entry for Whrilpool Laundry."""
    whirlpool_data: WhirlpoolData = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for washer in whirlpool_data.appliances_manager.washer_dryers:
        entities.extend(
            [
                Washer(
                    washer["SAID"],
                    washer["NAME"],
                    whirlpool_data.backend_selector,
                    whirlpool_data.auth,
                    description,
                )
                for description in SENSORS
            ]
        )

    if entities:
        async_add_entities(entities)


class Washer(Entity):
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
        self._attr_icon = ICON_W
        self._entity_description = description
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
        """Connect aircon to the cloud."""
        await self._wd.connect()

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        if self._entity_description.key == "timeremaining":
            value = int(
                self._entity_description.value_fn(
                    self._wd, "Cavity_TimeStatusEstTimeRemaining"
                )
            )

            if value == 3540:
                value = 0
            washertime = time.gmtime(value)
            return time.strftime("%M:%S", washertime)

        return self._entity_description.value_fn(self._wd).name
