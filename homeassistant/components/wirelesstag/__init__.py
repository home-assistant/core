"""Support for Wireless Sensor Tags."""
import asyncio
import logging

from wirelesstagpy import WirelessTags
from wirelesstagpy.exceptions import (
    WirelessTagsConnectionError,
    WirelessTagsException,
    WirelessTagsWrongCredentials,
)

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_ID,
    ATTR_VOLTAGE,
    CONF_PASSWORD,
    CONF_USERNAME,
    ELECTRIC_POTENTIAL_VOLT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)


# Strength of signal in dBm
ATTR_TAG_SIGNAL_STRENGTH = "signal_strength"
# Indicates if tag is out of range or not
ATTR_TAG_OUT_OF_RANGE = "out_of_range"
# Number in percents from max power of tag receiver
ATTR_TAG_POWER_CONSUMPTION = "power_consumption"
RETRY_INTERVAL = 60  # seconds

DOMAIN = "wirelesstag"
DEFAULT_ENTITY_NAMESPACE = "wirelesstag"

PLATFORMS = ["sensor", "binary_sensor"]

# Template for signal - first parameter is tag_id,
# second, tag manager mac address
SIGNAL_TAG_UPDATE = "wirelesstag.tag_info_updated_{}_{}"

# Template for signal - tag_id, sensor type and
# tag manager mac address
SIGNAL_BINARY_EVENT_UPDATE = "wirelesstag.binary_event_updated_{}_{}_{}"


class WirelessTagPlatform:
    """Principal object to manage all registered in HA tags."""

    def __init__(self, hass, api):
        """Designated initializer for wirelesstags platform."""
        self.hass = hass
        self.api = api
        self.tags = {}
        self._local_base_url = None

    def load_tags(self):
        """Load tags from remote server."""
        self.tags = self.api.load_tags()
        return self.tags

    def arm_sensor(self, sensor_type, tag_id, tag_manager_mac):
        """Arm sensor type for monitoring."""
        _LOGGER.debug("Arm sensor: %s", sensor_type)
        func_name = f"arm_{sensor_type}"
        arm_func = getattr(self.api, func_name)
        if arm_func is not None:
            arm_func(tag_id, tag_manager_mac)

    def disarm_sensor(self, sensor_type, tag_id, tag_manager_mac):
        """Disarm entity sensor monitoring."""
        _LOGGER.debug("Disarm sensor: %s", sensor_type)
        func_name = f"disarm_{sensor_type}"
        disarm_func = getattr(self.api, func_name)
        if disarm_func is not None:
            disarm_func(tag_id, tag_manager_mac)

    def start_monitoring(self):
        """Start monitoring push events."""

        def push_callback(tags_spec, event_spec):
            """Handle push update."""
            _LOGGER.debug(
                "Push notification arrived: %s, events: %s", tags_spec, event_spec
            )
            for uuid, tag in tags_spec.items():
                try:
                    tag_id = tag.tag_id
                    mac = tag.tag_manager_mac
                    _LOGGER.debug("Push notification for tag update arrived: %s", tag)
                    dispatcher_send(
                        self.hass, SIGNAL_TAG_UPDATE.format(tag_id, mac), tag
                    )
                    if uuid in event_spec:
                        events = event_spec[uuid]
                        for event in events:
                            _LOGGER.debug(
                                "Push notification for binary event arrived: %s", event
                            )
                            dispatcher_send(
                                self.hass,
                                SIGNAL_BINARY_EVENT_UPDATE.format(
                                    tag_id, event.type, mac
                                ),
                                tag,
                            )
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.error(
                        "Unable to handle tag update:\
                                %s error: %s",
                        str(tag),
                        str(ex),
                    )

        self.api.start_monitoring(push_callback)

    def stop_monitoring(self):
        """Stop cloud push monitoring."""
        _LOGGER.debug("Stop monitoring push updates for wirelesstags")
        self.api.stop_monitoring()

    @property
    def is_monitoring(self):
        """Check if monitoring is active."""
        return self.api.is_monitoring

    async def async_update_device_registry(self, tag, config_entry) -> None:
        """Update device registry."""
        _LOGGER.debug("Register device for tag: %s", tag)
        device_registry = await dr.async_get_registry(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, tag.uuid)},
            manufacturer="Wirelesstag",
            name=tag.name,
            model=f"Tag ({tag.tag_type})",
            sw_version=f"rev. {tag.sw_version}",
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Wirelesstags component."""
    if DOMAIN not in config:
        return True
    _LOGGER.debug("Setup Wirelesstags from YAML - %s", config[DOMAIN])
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wirelesstags from a config entry."""
    _LOGGER.debug("Setup config entry for Wirelesstags")
    try:
        username = entry.data[CONF_USERNAME]
        password = entry.data[CONF_PASSWORD]
        wirelesstags = WirelessTags(username=username, password=password)
        platform = WirelessTagPlatform(hass, wirelesstags)

        # try to authenticate during loading tags
        await hass.async_add_executor_job(platform.load_tags)

        hass.data[DOMAIN] = platform

        for tag in platform.tags.values():
            hass.async_create_task(platform.async_update_device_registry(tag, entry))

        hass.config_entries.async_setup_platforms(entry, PLATFORMS)
        register_services(hass)
        platform.start_monitoring()

        return True
    except (WirelessTagsWrongCredentials) as error:
        _LOGGER.error("Wrong creds for wirelesstag.net service: %s", str(error))
        raise ConfigEntryAuthFailed from error
    except (WirelessTagsConnectionError, asyncio.TimeoutError) as error:
        _LOGGER.error("Unable to connect to wirelesstag.net service: %s", str(error))
        raise ConfigEntryNotReady from error
    except Exception as error:
        _LOGGER.error("Failed to connect to wirelesstag.net service: %s", str(error))
        raise ConfigEntryNotReady from error


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading wirelesstags")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].stop_monitoring()
        hass.data[DOMAIN] = None

    return unload_ok


def register_services(hass):
    """Register tags services."""

    async def async_arm_monitoring(service):
        try:
            _LOGGER.info("Handle arm_monitoring service %s", service.data)
            await async_handle_monitoring(service, "arm_sensor")
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Unable to call arm_monitoring service: %s", ex)

    async def async_disarm_monitoring(service):
        """Handle disarm service request."""
        try:
            _LOGGER.info("Handle disarm_monitoring service %s", service.data)
            await async_handle_monitoring(service, "disarm_sensor")
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Unable to call disarm_monitoring service: %s", ex)

    async def async_handle_monitoring(service, selector):
        """Handle monitoring service request for specified selector."""
        type_monitor = service.data.get("type", "Motion")
        sensor_type = type_monitor.lower()
        platform = hass.data[DOMAIN]
        device_registry = dr.async_get(hass)
        device_ids = service.data.get(ATTR_DEVICE_ID)
        method_to_call = getattr(platform, selector)
        for device_id in device_ids:
            device = device_registry.async_get(device_id)
            uuid = list(device.identifiers)[0][1]
            if uuid in platform.tags:
                _LOGGER.info(
                    "Executing %s service for %s sensor", selector, sensor_type
                )
                tag = platform.tags[uuid]
                await hass.async_add_executor_job(
                    method_to_call, sensor_type, tag.tag_id, tag.tag_manager_mac
                )

    hass.services.async_register(DOMAIN, "arm_monitoring", async_arm_monitoring)
    hass.services.async_register(DOMAIN, "disarm_monitoring", async_disarm_monitoring)


class WirelessTagBaseSensor(Entity):
    """Base class for HA implementation for Wireless Sensor Tag."""

    def __init__(self, api, tag):
        """Initialize a base sensor for Wireless Sensor Tag platform."""
        self._api = api
        self._tag = tag
        self._uuid = self._tag.uuid
        self.tag_id = self._tag.tag_id
        self.tag_manager_mac = self._tag.tag_manager_mac
        self._name = self._tag.name
        self._state = 0

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def principal_value(self):
        """Return base value.

        Subclasses need override based on type of sensor.
        """
        return 0

    def updated_state_value(self):
        """Return formatted value.

        The default implementation formats principal value.
        """
        return self.decorate_value(self.principal_value)

    # pylint: disable=no-self-use
    def decorate_value(self, value):
        """Decorate input value to be well presented for end user."""
        return f"{value:.1f}"

    @property
    def available(self):
        """Return True if entity is available."""
        return self._tag.is_alive

    def update(self):
        """Update state."""
        if not self.should_poll:
            return

        try:
            updated_tags = self._api.load_tags()
            if (updated_tag := updated_tags[self._uuid]) is None:
                _LOGGER.error('Unable to update tag: "%s"', self.name)
                return

            self._tag = updated_tag
            self._state = self.updated_state_value()

            if self._api.is_monitoring is False:
                self._api.start_monitoring()
                _LOGGER.debug("Restore monitoring")
        except WirelessTagsException as ex:
            _LOGGER.debug("Unable to load tags with error: %s, stop monitoring", ex)
            self._api.stop_monitoring()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_BATTERY_LEVEL: int(self._tag.battery_remaining * 100),
            ATTR_VOLTAGE: f"{self._tag.battery_volts:.2f}{ELECTRIC_POTENTIAL_VOLT}",
            ATTR_TAG_SIGNAL_STRENGTH: f"{self._tag.signal_strength}{SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
            ATTR_TAG_OUT_OF_RANGE: not self._tag.is_in_range,
            ATTR_TAG_POWER_CONSUMPTION: f"{self._tag.power_consumption:.2f}{PERCENTAGE}",
        }
