"""Support for Xiaomi Mi Flora BLE plant sensor."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import btlewrap
from btlewrap import BluetoothBackendException
from miflora import miflora_poller
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONDUCTIVITY,
    CONF_FORCE_UPDATE,
    CONF_MAC,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_START,
    LIGHT_LUX,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

try:
    import bluepy.btle  # noqa: F401 pylint: disable=unused-import

    BACKEND = btlewrap.BluepyBackend
except ImportError:
    BACKEND = btlewrap.GatttoolBackend

_LOGGER = logging.getLogger(__name__)

CONF_ADAPTER = "adapter"
CONF_MEDIAN = "median"
CONF_GO_UNAVAILABLE_TIMEOUT = "go_unavailable_timeout"

DEFAULT_ADAPTER = "hci0"
DEFAULT_FORCE_UPDATE = False
DEFAULT_MEDIAN = 3
DEFAULT_NAME = "Mi Flora"
DEFAULT_GO_UNAVAILABLE_TIMEOUT = timedelta(seconds=7200)

SCAN_INTERVAL = timedelta(seconds=1200)

ATTR_LAST_SUCCESSFUL_UPDATE = "last_successful_update"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="light",
        name="Light intensity",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
    ),
    SensorEntityDescription(
        key="moisture",
        name="Moisture",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key="conductivity",
        name="Conductivity",
        native_unit_of_measurement=CONDUCTIVITY,
        icon="mdi:lightning-bolt-circle",
    ),
    SensorEntityDescription(
        key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MEDIAN, default=DEFAULT_MEDIAN): cv.positive_int,
        vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
        vol.Optional(CONF_ADAPTER, default=DEFAULT_ADAPTER): cv.string,
        vol.Optional(
            CONF_GO_UNAVAILABLE_TIMEOUT, default=DEFAULT_GO_UNAVAILABLE_TIMEOUT
        ): cv.time_period,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MiFlora sensor."""
    backend = BACKEND
    _LOGGER.debug("Miflora is using %s backend", backend.__name__)

    cache = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL).total_seconds()
    poller = miflora_poller.MiFloraPoller(
        config[CONF_MAC],
        cache_timeout=cache,
        adapter=config[CONF_ADAPTER],
        backend=backend,
    )
    force_update = config[CONF_FORCE_UPDATE]
    median = config[CONF_MEDIAN]

    go_unavailable_timeout = config[CONF_GO_UNAVAILABLE_TIMEOUT]

    prefix = config[CONF_NAME]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    entities = [
        MiFloraSensor(
            description,
            poller,
            prefix,
            force_update,
            median,
            go_unavailable_timeout,
        )
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]

    async_add_entities(entities)


class MiFloraSensor(SensorEntity):
    """Implementing the MiFlora sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        description: SensorEntityDescription,
        poller,
        prefix,
        force_update,
        median,
        go_unavailable_timeout,
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self.poller = poller
        self.data: list[Any] = []
        if prefix:
            self._attr_name = f"{prefix} {description.name}"
        self._attr_force_update = force_update
        self.go_unavailable_timeout = go_unavailable_timeout
        self.last_successful_update = dt_util.utc_from_timestamp(0)
        # Median is used to filter out outliers. median of 3 will filter
        # single outliers, while  median of 5 will filter double outliers
        # Use median_count = 1 if no filtering is required.
        self.median_count = median

    async def async_added_to_hass(self):
        """Set initial state."""

        @callback
        def on_startup(_):
            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, on_startup)

    @property
    def available(self):
        """Return True if did update since 2h."""
        return self.last_successful_update > (
            dt_util.utcnow() - self.go_unavailable_timeout
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return {ATTR_LAST_SUCCESSFUL_UPDATE: self.last_successful_update}

    def update(self):
        """
        Update current conditions.

        This uses a rolling median over 3 values to filter out outliers.
        """
        try:
            _LOGGER.debug("Polling data for %s", self.name)
            data = self.poller.parameter_value(self.entity_description.key)
        except (OSError, BluetoothBackendException) as err:
            _LOGGER.info("Polling error %s: %s", type(err).__name__, err)
            return

        if data is not None:
            _LOGGER.debug("%s = %s", self.name, data)
            self.data.append(data)
            self.last_successful_update = dt_util.utcnow()
        else:
            _LOGGER.info("Did not receive any data from Mi Flora sensor %s", self.name)
            # Remove old data from median list or set sensor value to None
            # if no data is available anymore
            if self.data:
                self.data = self.data[1:]
            else:
                self._attr_native_value = None
            return

        _LOGGER.debug("Data collected: %s", self.data)
        if len(self.data) > self.median_count:
            self.data = self.data[1:]

        if len(self.data) == self.median_count:
            median = sorted(self.data)[int((self.median_count - 1) / 2)]
            _LOGGER.debug("Median is: %s", median)
            self._attr_native_value = median
        elif self._attr_native_value is None:
            _LOGGER.debug("Set initial state")
            self._attr_native_value = self.data[0]
        else:
            _LOGGER.debug("Not yet enough data for median calculation")
