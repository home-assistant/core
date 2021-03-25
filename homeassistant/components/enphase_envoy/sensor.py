"""Support for Enphase Envoy solar energy monitor."""

from datetime import timedelta
import logging

import async_timeout
from envoy_reader.envoy_reader import EnvoyReader
import httpx
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    ENERGY_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)

SENSORS = {
    "production": ("Envoy Current Energy Production", POWER_WATT),
    "daily_production": ("Envoy Today's Energy Production", ENERGY_WATT_HOUR),
    "seven_days_production": (
        "Envoy Last Seven Days Energy Production",
        ENERGY_WATT_HOUR,
    ),
    "lifetime_production": ("Envoy Lifetime Energy Production", ENERGY_WATT_HOUR),
    "consumption": ("Envoy Current Energy Consumption", POWER_WATT),
    "daily_consumption": ("Envoy Today's Energy Consumption", ENERGY_WATT_HOUR),
    "seven_days_consumption": (
        "Envoy Last Seven Days Energy Consumption",
        ENERGY_WATT_HOUR,
    ),
    "lifetime_consumption": ("Envoy Lifetime Energy Consumption", ENERGY_WATT_HOUR),
    "inverters": ("Envoy Inverter", POWER_WATT),
}

ICON = "mdi:flash"
CONST_DEFAULT_HOST = "envoy"

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_IP_ADDRESS, default=CONST_DEFAULT_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default="envoy"): cv.string,
        vol.Optional(CONF_PASSWORD, default=""): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)): vol.All(
            cv.ensure_list, [vol.In(list(SENSORS))]
        ),
        vol.Optional(CONF_NAME, default=""): cv.string,
    }
)


async def async_setup_platform(
    homeassistant, config, async_add_entities, discovery_info=None
):
    """Set up the Enphase Envoy sensor."""
    ip_address = config[CONF_IP_ADDRESS]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    name = config[CONF_NAME]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    if "inverters" in monitored_conditions:
        envoy_reader = EnvoyReader(ip_address, username, password, inverters=True)
    else:
        envoy_reader = EnvoyReader(ip_address, username, password)

    try:
        await envoy_reader.getData()
    except httpx.HTTPStatusError as err:
        _LOGGER.error("Authentication failure during setup: %s", err)
        return
    except httpx.HTTPError as err:
        raise PlatformNotReady from err

    async def async_update_data():
        """Fetch data from API endpoint."""
        data = {}
        async with async_timeout.timeout(30):
            try:
                await envoy_reader.getData()
            except httpx.HTTPError as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

            for condition in monitored_conditions:
                if condition != "inverters":
                    data[condition] = await getattr(envoy_reader, condition)()
                else:
                    data["inverters_production"] = await getattr(
                        envoy_reader, "inverters_production"
                    )()

            _LOGGER.debug("Retrieved data from API: %s", data)

            return data

    coordinator = DataUpdateCoordinator(
        homeassistant,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_refresh()

    if coordinator.data is None:
        raise PlatformNotReady

    entities = []
    for condition in monitored_conditions:
        entity_name = ""
        if (
            condition == "inverters"
            and coordinator.data.get("inverters_production") is not None
        ):
            for inverter in coordinator.data["inverters_production"]:
                entity_name = f"{name}{SENSORS[condition][0]} {inverter}"
                split_name = entity_name.split(" ")
                serial_number = split_name[-1]
                entities.append(
                    Envoy(
                        condition,
                        entity_name,
                        serial_number,
                        SENSORS[condition][1],
                        coordinator,
                    )
                )
        elif condition != "inverters":
            entity_name = f"{name}{SENSORS[condition][0]}"
            entities.append(
                Envoy(
                    condition,
                    entity_name,
                    None,
                    SENSORS[condition][1],
                    coordinator,
                )
            )

    async_add_entities(entities)


class Envoy(CoordinatorEntity, SensorEntity):
    """Envoy entity."""

    def __init__(self, sensor_type, name, serial_number, unit, coordinator):
        """Initialize Envoy entity."""
        self._type = sensor_type
        self._name = name
        self._serial_number = serial_number
        self._unit_of_measurement = unit

        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._type != "inverters":
            value = self.coordinator.data.get(self._type)

        elif (
            self._type == "inverters"
            and self.coordinator.data.get("inverters_production") is not None
        ):
            value = self.coordinator.data.get("inverters_production").get(
                self._serial_number
            )[0]
        else:
            return None

        return value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if (
            self._type == "inverters"
            and self.coordinator.data.get("inverters_production") is not None
        ):
            value = self.coordinator.data.get("inverters_production").get(
                self._serial_number
            )[1]
            return {"last_reported": value}

        return None
