"""Support for Tesla cars."""
from collections import defaultdict
import logging

import voluptuous as vol
from teslajsonpy import (
    Controller as teslaAPI,
    TeslaException,
    __version__ as teslajsonpy_version,
)


from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from .config_flow import configured_instances

DOMAIN = "tesla"

_LOGGER = logging.getLogger(__name__)

TESLA_ID_FORMAT = "{}_{}"
TESLA_ID_LIST_SCHEMA = vol.Schema([int])

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=300): vol.All(
                    cv.positive_int, vol.Clamp(min=300)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

NOTIFICATION_ID = "tesla_integration_notification"
NOTIFICATION_TITLE = "Tesla integration setup"

TESLA_COMPONENTS = [
    "sensor",
    "lock",
    "climate",
    "binary_sensor",
    "device_tracker",
    "switch",
]


def setup(hass, base_config):
    """Set up of Tesla component."""
    config = base_config.get(DOMAIN)
    if not config:
        return True
    email = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    update_interval = config.get(CONF_SCAN_INTERVAL)
    if email in configured_instances(hass):
        for entry in hass.config_entries.async_entries(DOMAIN):
            if email == entry.title:
                hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_USERNAME: email,
                        CONF_PASSWORD: password,
                        CONF_SCAN_INTERVAL: update_interval,
                    },
                )
                break
    else:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_USERNAME: email,
                    CONF_PASSWORD: password,
                    CONF_SCAN_INTERVAL: update_interval,
                },
            )
        )
    return True


def setup_entry(hass, config_entry):
    """Set up Tesla as config entry."""

    _LOGGER.info("Loaded teslajsonpy==%s", teslajsonpy_version)
    if DOMAIN not in hass.data:
        config = config_entry.data
        try:
            controller = teslaAPI(
                config[CONF_USERNAME], config[CONF_PASSWORD], config[CONF_SCAN_INTERVAL]
            )
            hass.data[DOMAIN] = {"controller": controller, "devices": defaultdict(list)}
            _LOGGER.debug("Connected to the Tesla API.")
        except TeslaException as ex:
            if ex.code == 401:
                hass.components.persistent_notification.create(
                    "Error:<br />Please check username and password."
                    "Please remove and readd the Integration.",
                    title=NOTIFICATION_TITLE,
                    notification_id=NOTIFICATION_ID,
                )
            else:
                hass.components.persistent_notification.create(
                    "Error:<br />Can't communicate with Tesla API.<br />"
                    "Error code: {} Reason: {}"
                    "Please remove and readd the Integration.",
                    "".format(ex.code, ex.message),
                    title=NOTIFICATION_TITLE,
                    notification_id=NOTIFICATION_ID,
                )
            _LOGGER.warning("Unable to communicate with Tesla API: %s", ex.message)
            return False
        except BaseException as ex:
            _LOGGER.warning("Unknown error: %s", ex)
            return False
    all_devices = hass.data[DOMAIN]["controller"].list_vehicles()

    if not all_devices:
        return False

    for device in all_devices:
        hass.data[DOMAIN]["devices"][device.hass_type].append(device)

    for component in TESLA_COMPONENTS:
        hass.async_add_job(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Tesla as config entry."""
    return await hass.async_add_executor_job(setup_entry, hass, config_entry)


async def async_unload_entry(hass, entry) -> bool:
    """Unload a config entry."""
    for component in TESLA_COMPONENTS:
        _LOGGER.debug("Attemping to unload %s", component)
        if component == "device_tracker":
            await hass.data[DOMAIN]["devices"]["device_tracker"].unload()
        else:
            await hass.config_entries.async_forward_entry_unload(entry, component)
    username = entry.data["username"]
    hass.data.pop(DOMAIN)
    _LOGGER.debug("Unloaded entry for %s", username)
    return True


class TeslaDevice(Entity):
    """Representation of a Tesla device."""

    def __init__(self, tesla_device, controller):
        """Initialise of the Tesla device."""
        self.tesla_device = tesla_device
        self.controller = controller
        self._name = self.tesla_device.name
        self.tesla_id = slugify(self.tesla_device.uniq_name)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.tesla_id

    @property
    def should_poll(self):
        """Return the polling state."""
        return self.tesla_device.should_poll

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}

        if self.tesla_device.has_battery():
            attr[ATTR_BATTERY_LEVEL] = self.tesla_device.battery_level()
        return attr

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.tesla_device.id())},
            "name": self.tesla_device.car_name(),
            "manufacturer": "Tesla",
            "model": self.tesla_device.car_type,
            "sw_version": self.tesla_device.car_version,
        }
