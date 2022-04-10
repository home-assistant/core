"""Support for Eight smart mattress covers and mattresses."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Union

from pyeight.eight import EightSleep
from pyeight.user import EightUser
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_BINARY_SENSORS,
    CONF_PASSWORD,
    CONF_SENSORS,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

DATA_EIGHT = "eight_sleep"
DATA_HEAT = "heat"
DATA_USER = "user"
DATA_API = "api"
DOMAIN = "eight_sleep"

HEAT_ENTITY = "heat"
USER_ENTITY = "user"


HEAT_SCAN_INTERVAL = timedelta(seconds=60)
USER_SCAN_INTERVAL = timedelta(seconds=300)

NAME_MAP = {
    "left_current_sleep": "Left Sleep Session",
    "left_current_sleep_fitness": "Left Sleep Fitness",
    "left_last_sleep": "Left Previous Sleep Session",
    "right_current_sleep": "Right Sleep Session",
    "right_current_sleep_fitness": "Right Sleep Fitness",
    "right_last_sleep": "Right Previous Sleep Session",
}

SENSORS = [
    "current_sleep",
    "current_sleep_fitness",
    "last_sleep",
    "bed_state",
    "bed_temperature",
    "sleep_stage",
]

SERVICE_HEAT_SET = "heat_set"

ATTR_TARGET_HEAT = "target"
ATTR_HEAT_DURATION = "duration"

VALID_TARGET_HEAT = vol.All(vol.Coerce(int), vol.Clamp(min=-100, max=100))
VALID_DURATION = vol.All(vol.Coerce(int), vol.Clamp(min=0, max=28800))

SERVICE_EIGHT_SCHEMA = vol.Schema(
    {
        ATTR_ENTITY_ID: cv.entity_ids,
        ATTR_TARGET_HEAT: VALID_TARGET_HEAT,
        ATTR_HEAT_DURATION: VALID_DURATION,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


def _get_device_unique_id(eight: EightSleep, user_obj: EightUser | None = None) -> str:
    """Get the device's unique ID."""
    unique_id = eight.deviceid
    if user_obj:
        unique_id = f"{unique_id}.{user_obj.userid}.{user_obj.side}"
    return unique_id


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Eight Sleep component."""

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    user = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant")
        return False

    timezone = str(hass.config.time_zone)

    eight = EightSleep(user, password, timezone, async_get_clientsession(hass))

    hass.data.setdefault(DATA_EIGHT, {})[DATA_API] = eight

    # Authenticate, build sensors
    success = await eight.start()
    if not success:
        # Authentication failed, cannot continue
        return False

    heat_coordinator = hass.data[DOMAIN][DATA_HEAT] = EightSleepHeatDataCoordinator(
        hass, eight
    )
    user_coordinator = hass.data[DOMAIN][DATA_USER] = EightSleepUserDataCoordinator(
        hass, eight
    )
    await heat_coordinator.async_config_entry_first_refresh()
    await user_coordinator.async_config_entry_first_refresh()

    # Load sub components
    sensors = []
    binary_sensors = []
    if eight.users:
        for user, obj in eight.users.items():
            for sensor in SENSORS:
                sensors.append((obj.side, sensor))
            binary_sensors.append((obj.side, "bed_presence"))
        sensors.append((None, "room_temperature"))
    else:
        # No users, cannot continue
        return False

    hass.async_create_task(
        discovery.async_load_platform(
            hass, Platform.SENSOR, DOMAIN, {CONF_SENSORS: sensors}, config
        )
    )

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.BINARY_SENSOR,
            DOMAIN,
            {CONF_BINARY_SENSORS: binary_sensors},
            config,
        )
    )

    async def async_service_handler(service: ServiceCall) -> None:
        """Handle eight sleep service calls."""
        params = service.data.copy()

        sensor = params.pop(ATTR_ENTITY_ID, None)
        target = params.pop(ATTR_TARGET_HEAT, None)
        duration = params.pop(ATTR_HEAT_DURATION, 0)

        for sens in sensor:
            side = sens.split("_")[1]
            userid = eight.fetch_userid(side)
            usrobj = eight.users[userid]
            await usrobj.set_heating_level(target, duration)

        await heat_coordinator.async_request_refresh()

    # Register services
    hass.services.async_register(
        DOMAIN, SERVICE_HEAT_SET, async_service_handler, schema=SERVICE_EIGHT_SCHEMA
    )

    return True


class EightSleepHeatDataCoordinator(DataUpdateCoordinator):
    """Class to retrieve heat data from Eight Sleep."""

    def __init__(self, hass: HomeAssistant, api: EightSleep) -> None:
        """Initialize coordinator."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_heat",
            update_interval=HEAT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        await self.api.update_device_data()


class EightSleepUserDataCoordinator(DataUpdateCoordinator):
    """Class to retrieve user data from Eight Sleep."""

    def __init__(self, hass: HomeAssistant, api: EightSleep) -> None:
        """Initialize coordinator."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_user",
            update_interval=USER_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        await self.api.update_user_data()


class EightSleepBaseEntity(
    CoordinatorEntity[
        Union[EightSleepUserDataCoordinator, EightSleepHeatDataCoordinator]
    ]
):
    """The base Eight Sleep entity class."""

    def __init__(
        self,
        name: str,
        coordinator: EightSleepUserDataCoordinator | EightSleepHeatDataCoordinator,
        eight: EightSleep,
        side: str | None,
        sensor: str,
    ) -> None:
        """Initialize the data object."""
        super().__init__(coordinator)
        self._eight = eight
        self._side = side
        self._sensor = sensor
        self._usrobj: EightUser | None = None
        if self._side:
            self._usrobj = self._eight.users[self._eight.fetch_userid(self._side)]
        full_sensor_name = self._sensor
        if self._side is not None:
            full_sensor_name = f"{self._side}_{full_sensor_name}"
        mapped_name = NAME_MAP.get(
            full_sensor_name, full_sensor_name.replace("_", " ").title()
        )

        self._attr_name = f"{name} {mapped_name}"
        self._attr_unique_id = (
            f"{_get_device_unique_id(eight, self._usrobj)}.{self._sensor}"
        )


class EightSleepUserEntity(EightSleepBaseEntity):
    """The Eight Sleep user entity."""

    def __init__(
        self,
        name: str,
        coordinator: EightSleepUserDataCoordinator,
        eight: EightSleep,
        side: str | None,
        sensor: str,
        units: str,
    ) -> None:
        """Initialize the data object."""
        super().__init__(name, coordinator, eight, side, sensor)
        self._units = units
