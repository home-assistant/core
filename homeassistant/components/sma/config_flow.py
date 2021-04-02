"""Config flow for the sma integration."""
import logging

import aiohttp
import pysma
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SENSORS,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CUSTOM,
    CONF_FACTOR,
    CONF_GROUP,
    CONF_KEY,
    CONF_UNIT,
    DEVICE_INFO,
    GROUPS,
)
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data: dict):
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass, verify_ssl=data[CONF_VERIFY_SSL])

    protocol = "https" if data[CONF_SSL] else "http"
    url = f"{protocol}://{data[CONF_HOST]}"

    sma = pysma.SMA(session, url, data[CONF_PASSWORD], group=data[CONF_GROUP])

    if await sma.new_session() is False:
        raise InvalidAuth

    device_info = await sma.device_info()

    if not device_info:
        raise CannotRetrieveDeviceInfo

    await sma.close_session()
    return device_info


class SmaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMA."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self._data = {
            CONF_HOST: vol.UNDEFINED,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_GROUP: GROUPS[0],
            CONF_PASSWORD: vol.UNDEFINED,
            CONF_SENSORS: [],
            CONF_CUSTOM: {},
            DEVICE_INFO: {},
        }

    async def async_step_user(self, user_input=None):
        """First step in config flow."""
        errors = {}
        if user_input is not None:
            self._data[CONF_HOST] = user_input[CONF_HOST]
            self._data[CONF_SSL] = user_input[CONF_SSL]
            self._data[CONF_VERIFY_SSL] = user_input[CONF_VERIFY_SSL]
            self._data[CONF_GROUP] = user_input[CONF_GROUP]
            self._data[CONF_PASSWORD] = user_input[CONF_PASSWORD]

            try:
                self._data[DEVICE_INFO] = await validate_input(self.hass, user_input)
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotRetrieveDeviceInfo:
                errors["base"] = "cannot_retrieve_device_info"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(self._data[DEVICE_INFO]["serial"])
                self._abort_if_unique_id_configured()
                return await self.async_step_sensors()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._data[CONF_HOST]): cv.string,
                    vol.Optional(CONF_SSL, default=self._data[CONF_SSL]): cv.boolean,
                    vol.Optional(
                        CONF_VERIFY_SSL, default=self._data[CONF_VERIFY_SSL]
                    ): cv.boolean,
                    vol.Optional(CONF_GROUP, default=self._data[CONF_GROUP]): vol.In(
                        GROUPS
                    ),
                    vol.Required(
                        CONF_PASSWORD, default=self._data[CONF_PASSWORD]
                    ): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_sensors(self, user_input=None):
        """Second step in config flow to select sensors to create."""
        errors = {}
        if user_input is not None:
            self._data[CONF_SENSORS] = user_input[CONF_SENSORS]
            return self.async_create_entry(title=self._data[CONF_HOST], data=self._data)

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SENSORS, default=self._data[CONF_SENSORS]
                    ): cv.multi_select({s.name: s.name for s in pysma.Sensors()})
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config=None):
        """Import a config flow from configuration."""
        device_info = await validate_input(self.hass, import_config)
        config_entry_unique_id = device_info["serial"]
        import_config[DEVICE_INFO] = device_info

        config_sensors = import_config[CONF_SENSORS].copy()

        # find and replace sensors removed from pysma
        for sensor in config_sensors:
            if sensor in pysma.LEGACY_MAP:
                import_config[CONF_SENSORS].remove(sensor)
                import_config[CONF_SENSORS].append(
                    pysma.LEGACY_MAP[sensor]["new_sensor"]
                )

        # If unique is configured import was already run
        # This means remap was already done, so we can abort
        await self.async_set_unique_id(config_entry_unique_id)
        self._abort_if_unique_id_configured(import_config)

        entity_registry = er.async_get(self.hass)

        # Init all default sensors
        sensor_def = pysma.Sensors()

        # Add sensors from the custom config
        sensor_def.add(
            [
                pysma.Sensor(
                    o[CONF_KEY], n, o[CONF_UNIT], o[CONF_FACTOR], o.get(CONF_PATH)
                )
                for n, o in import_config[CONF_CUSTOM].items()
            ]
        )

        # Create list of all possible sensor names
        possible_sensors = list(
            set(config_sensors + [s.name for s in sensor_def] + list(pysma.LEGACY_MAP))
        )

        # Find entity_id using previous format of unique ID and change to new unique ID
        for sensor in possible_sensors:
            if sensor in sensor_def:
                pysma_sensor = sensor_def[sensor]
                original_key = pysma_sensor.key
            elif sensor in pysma.LEGACY_MAP:
                # If sensor was removed from pysma we will remap it to the new sensor
                legacy_sensor = pysma.LEGACY_MAP[sensor]
                pysma_sensor = sensor_def[legacy_sensor["new_sensor"]]
                original_key = legacy_sensor["old_key"]
            else:
                _LOGGER.error("%s does not exist", sensor)
                continue

            entity_id = entity_registry.async_get_entity_id(
                "sensor", "sma", f"sma-{original_key}-{sensor}"
            )
            if entity_id:
                new_unique_id = f"{config_entry_unique_id}-{pysma_sensor.key}_{pysma_sensor.key_idx}"
                entity_registry.async_update_entity(
                    entity_id, new_unique_id=new_unique_id
                )

        return self.async_create_entry(
            title=import_config[CONF_HOST], data=import_config
        )


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CannotRetrieveDeviceInfo(exceptions.HomeAssistantError):
    """Error to indicate we cannot retrieve the device information."""
