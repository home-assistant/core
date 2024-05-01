"""Support for interacting with Vultr subscriptions."""

from __future__ import annotations

import logging
from typing import Any

from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

from . import (
    ATTR_ALLOWED_BANDWIDTH,
    ATTR_CREATED_AT,
    ATTR_DISK,
    ATTR_INSTANCE_ID,
    ATTR_INSTANCE_LABEL,
    ATTR_IPV4_ADDRESS,
    ATTR_MEMORY,
    ATTR_OS,
    ATTR_REGION,
    ATTR_VCPUS,
    CONF_INSTANCE_ID,
    DEFAULT_NAME,
    MIN_TIME_BETWEEN_UPDATES,
    Vultr,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_INSTANCE_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Vultr subscription switch."""
    api_key = config.get(CONF_API_KEY)
    instance_id = config.get(CONF_INSTANCE_ID)
    name = config.get(CONF_NAME)
    try:
        assert api_key
        vultr_data = VultrData(api_key, instance_id)
    except Exception as ex:
        _LOGGER.error("Failed to make update API request because: %s", ex)
        raise PlatformNotReady from ex

    add_entities([VultrSwitch(vultr_data, instance_id, name)], True)


class VultrSwitch(SwitchEntity):
    """Representation of a Vultr subscription switch."""

    def __init__(self, vultr, instance_id, name):
        """Initialize a new Vultr switch."""
        self._vultr_data: VultrData = vultr
        self._name = name
        self.instance_id = instance_id

    @property
    def name(self):
        """Return the name of the switch."""
        try:
            return self._name.format(self._vultr_data.data["label"])
        except (TypeError, KeyError):
            return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._vultr_data.data["power_status"] == "running"

    @property
    def icon(self):
        """Return the icon of this server."""
        return "mdi:server" if self.is_on else "mdi:server-off"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the Vultr subscription."""
        return {
            ATTR_ALLOWED_BANDWIDTH: self._vultr_data.data.get("allowed_bandwidth"),
            ATTR_CREATED_AT: self._vultr_data.data.get("date_created"),
            ATTR_DISK: self._vultr_data.data.get("disk"),
            ATTR_IPV4_ADDRESS: self._vultr_data.data.get("main_ip"),
            ATTR_MEMORY: self._vultr_data.data.get("ram"),
            ATTR_OS: self._vultr_data.data.get("os"),
            ATTR_REGION: self._vultr_data.data.get("region"),
            ATTR_INSTANCE_ID: self._vultr_data.data.get("id"),
            ATTR_INSTANCE_LABEL: self._vultr_data.data.get("label"),
            ATTR_VCPUS: self._vultr_data.data.get("vcpu_count"),
        }

    def turn_on(self, **kwargs: Any) -> None:
        """Boot-up the subscription."""
        if self._vultr_data.data["power_status"] != "running":
            self._vultr_data.client.start(self.instance_id)

    def turn_off(self, **kwargs: Any) -> None:
        """Halt the subscription."""
        if self._vultr_data.data["power_status"] == "running":
            self._vultr_data.client.halt(self.instance_id)

    def update(self) -> None:
        """Get the latest data from the device and update the data."""
        self._vultr_data.update()


class VultrData:
    """Vultr Switch Data."""

    def __init__(self, api_key, instance_id):
        """Initialize the data object."""
        self.client = Vultr(api_key)
        self.data = {}
        self.instance_id = instance_id

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Use the data from Vultr API."""
        try:
            self.data = self.client.get_instance(self.instance_id)
        except RequestException as exp:
            _LOGGER.error("Error on receive last Vultr data: %s", exp)
