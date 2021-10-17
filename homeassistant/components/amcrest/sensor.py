"""Support for Amcrest IP camera sensors."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from amcrest import AmcrestError

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import CONF_NAME, CONF_SENSORS, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DATA_AMCREST, DEVICES, SENSOR_SCAN_INTERVAL_SECS, SERVICE_UPDATE
from .helpers import log_update_error, service_signal

if TYPE_CHECKING:
    from . import AmcrestDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=SENSOR_SCAN_INTERVAL_SECS)

SENSOR_PTZ_PRESET = "ptz_preset"
SENSOR_SDCARD = "sdcard"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_PTZ_PRESET,
        name="PTZ Preset",
        icon="mdi:camera-iris",
    ),
    SensorEntityDescription(
        key=SENSOR_SDCARD,
        name="SD Used",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:sd",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for an Amcrest IP Camera."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][name]
    sensors = discovery_info[CONF_SENSORS]
    async_add_entities(
        [
            AmcrestSensor(name, device, description)
            for description in SENSOR_TYPES
            if description.key in sensors
        ],
        True,
    )


class AmcrestSensor(SensorEntity):
    """A sensor implementation for Amcrest IP camera."""

    def __init__(
        self, name: str, device: AmcrestDevice, description: SensorEntityDescription
    ) -> None:
        """Initialize a sensor for Amcrest camera."""
        self.entity_description = description
        self._signal_name = name
        self._api = device.api
        self._channel = device.channel
        self._unsub_dispatcher: Callable[[], None] | None = None

        self._attr_name = f"{name} {description.name}"
        self._attr_extra_state_attributes = {}

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._api.available

    def update(self) -> None:
        """Get the latest data and updates the state."""
        if not self.available:
            return
        _LOGGER.debug("Updating %s sensor", self.name)

        sensor_type = self.entity_description.key
        if self._attr_unique_id is None:
            serial_number = self._api.serial_number
            if serial_number:
                self._attr_unique_id = f"{serial_number}-{sensor_type}-{self._channel}"

        try:
            if self._attr_unique_id is None:
                serial_number = self._api.serial_number
                if serial_number:
                    self._attr_unique_id = (
                        f"{serial_number}-{sensor_type}-{self._channel}"
                    )

            if sensor_type == SENSOR_PTZ_PRESET:
                self._attr_native_value = self._api.ptz_presets_count

            elif sensor_type == SENSOR_SDCARD:
                storage = self._api.storage_all
                try:
                    self._attr_extra_state_attributes[
                        "Total"
                    ] = f"{storage['total'][0]:.2f} {storage['total'][1]}"
                except ValueError:
                    self._attr_extra_state_attributes[
                        "Total"
                    ] = f"{storage['total'][0]} {storage['total'][1]}"
                try:
                    self._attr_extra_state_attributes[
                        "Used"
                    ] = f"{storage['used'][0]:.2f} {storage['used'][1]}"
                except ValueError:
                    self._attr_extra_state_attributes[
                        "Used"
                    ] = f"{storage['used'][0]} {storage['used'][1]}"
                try:
                    self._attr_native_value = f"{storage['used_percent']:.2f}"
                except ValueError:
                    self._attr_native_value = storage["used_percent"]
        except AmcrestError as error:
            log_update_error(_LOGGER, "update", self.name, "sensor", error)

    async def async_on_demand_update(self) -> None:
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self) -> None:
        """Subscribe to update signal."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            service_signal(SERVICE_UPDATE, self._signal_name),
            self.async_on_demand_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect from update signal."""
        assert self._unsub_dispatcher is not None
        self._unsub_dispatcher()
