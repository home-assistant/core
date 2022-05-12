"""Support for Eight smart mattress covers and mattresses."""
from __future__ import annotations

from datetime import timedelta
import logging

from pyeight.eight import EightSleep
from pyeight.user import EightUser
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    ATTR_HEAT_DURATION,
    ATTR_TARGET_HEAT,
    DATA_API,
    DATA_HEAT,
    DATA_USER,
    DOMAIN,
    NAME_MAP,
    SERVICE_HEAT_SET,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

HEAT_SCAN_INTERVAL = timedelta(seconds=60)
USER_SCAN_INTERVAL = timedelta(seconds=300)

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

    eight = EightSleep(
        user, password, hass.config.time_zone, async_get_clientsession(hass)
    )

    hass.data.setdefault(DOMAIN, {})

    # Authenticate, build sensors
    success = await eight.start()
    if not success:
        # Authentication failed, cannot continue
        return False

    heat_coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_heat",
        update_interval=HEAT_SCAN_INTERVAL,
        update_method=eight.update_device_data,
    )
    user_coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_user",
        update_interval=USER_SCAN_INTERVAL,
        update_method=eight.update_user_data,
    )
    await heat_coordinator.async_config_entry_first_refresh()
    await user_coordinator.async_config_entry_first_refresh()

    if not eight.users:
        # No users, cannot continue
        return False

    hass.data[DOMAIN] = {
        DATA_API: eight,
        DATA_HEAT: heat_coordinator,
        DATA_USER: user_coordinator,
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            discovery.async_load_platform(hass, platform, DOMAIN, {}, config)
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


class EightSleepBaseEntity(CoordinatorEntity[DataUpdateCoordinator]):
    """The base Eight Sleep entity class."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        eight: EightSleep,
        user_id: str | None,
        sensor: str,
    ) -> None:
        """Initialize the data object."""
        super().__init__(coordinator)
        self._eight = eight
        self._user_id = user_id
        self._sensor = sensor
        self._user_obj: EightUser | None = None
        if self._user_id:
            self._user_obj = self._eight.users[user_id]

        mapped_name = NAME_MAP.get(sensor, sensor.replace("_", " ").title())
        if self._user_obj is not None:
            mapped_name = f"{self._user_obj.side.title()} {mapped_name}"

        self._attr_name = f"Eight {mapped_name}"
        self._attr_unique_id = (
            f"{_get_device_unique_id(eight, self._user_obj)}.{sensor}"
        )
