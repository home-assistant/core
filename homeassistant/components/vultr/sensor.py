"""Support for monitoring the state of Vultr Subscriptions."""

from __future__ import annotations

import logging

from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

from . import (
    ATTR_ACCOUNT_BALANCE,
    ATTR_CURRENT_BANDWIDTH_IN,
    ATTR_CURRENT_BANDWIDTH_OUT,
    ATTR_PENDING_CHARGES,
    DEFAULT_NAME,
    MIN_TIME_BETWEEN_UPDATES,
    Vultr,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTR_CURRENT_BANDWIDTH_OUT,
        name="Current Bandwidth Out",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key=ATTR_CURRENT_BANDWIDTH_IN,
        name="Current Bandwidth In",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key=ATTR_PENDING_CHARGES,
        name="Pending Charges",
        native_unit_of_measurement="US$",
        icon="mdi:currency-usd",
    ),
    SensorEntityDescription(
        key=ATTR_ACCOUNT_BALANCE,
        name="Account Balance",
        native_unit_of_measurement="US$",
        icon="mdi:currency-usd",
    ),
)
SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Vultr subscription (server) sensor."""
    api_key = config.get(CONF_API_KEY)
    try:
        assert api_key
        vultr_data = VultrData(api_key)
    except Exception as ex:
        _LOGGER.error("Failed to make update API request because: %s", ex)
        raise PlatformNotReady from ex

    name = config[CONF_NAME]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]

    entities: list[SensorEntity] = []
    for description in SENSOR_TYPES:
        if description.key in monitored_conditions:
            if description.key == ATTR_CURRENT_BANDWIDTH_IN:
                entities.append(AccountBandwidthInSensor(vultr_data, name, description))
            elif description.key == ATTR_CURRENT_BANDWIDTH_OUT:
                entities.append(
                    AccountBandwidthOutSensor(vultr_data, name, description)
                )
            elif description.key in [ATTR_PENDING_CHARGES, ATTR_ACCOUNT_BALANCE]:
                entities.append(AccountInfoSensor(vultr_data, name, description))
            else:
                _LOGGER.error("Unrecognized monitor condition %s", description.key)
                return

    add_entities(entities, True)


class AccountInfoSensor(SensorEntity):
    """Representation of a Vultr subscription sensor."""

    def __init__(self, vultr_data, name, description: SensorEntityDescription) -> None:
        """Initialize a new Vultr sensor."""
        self.entity_description = description
        self._vultr_data = vultr_data
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        try:
            return self._name.format(self.entity_description.name)
        except IndexError:
            try:
                return self._name.format(
                    self._vultr_data.account.get("name"), self.entity_description.name
                )
            except (KeyError, TypeError):
                return self._name

    @property
    def native_value(self):
        """Return the value of this given sensor type."""
        try:
            return round(
                float(self._vultr_data.account.get(self.entity_description.key)), 2
            )
        except (TypeError, ValueError):
            return self._vultr_data.account.get(self.entity_description.key)

    def update(self) -> None:
        """Update state of sensor."""
        self._vultr_data.update()


class AccountBandwidthSensor(SensorEntity):
    """Representation of a Vultr Account sensor."""

    def __init__(self, vultr_data, name, description: SensorEntityDescription) -> None:
        """Initialize a new Vultr sensor."""
        self.entity_description = description
        self._vultr_data = vultr_data
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        try:
            return self._name.format(self.entity_description.name)
        except IndexError:
            try:
                return self._name.format(
                    self._vultr_data.account["name"], self.entity_description.name
                )
            except (KeyError, TypeError):
                return self._name

    def update(self) -> None:
        """Update state of sensor."""
        self._vultr_data.update()


class AccountBandwidthInSensor(AccountBandwidthSensor):
    """Vultr Account Current Month Bandwidth In Info."""

    @property
    def native_value(self):
        """Return the value of this given sensor type."""
        try:
            v = self._vultr_data.bandwidth["gb_in"]
            return round(float(v), 2)
        except (TypeError, ValueError):
            return 0


class AccountBandwidthOutSensor(AccountBandwidthSensor):
    """Vultr Account Current Month Bandwidth Out Info."""

    @property
    def native_value(self):
        """Return the value of this given sensor type."""
        try:
            v = self._vultr_data.bandwidth["gb_out"]
            return round(float(v), 2)
        except (TypeError, ValueError):
            return 0


class VultrData:
    """Vultr Sensor Data."""

    def __init__(self, api_key):
        """Initialize the data object."""
        self.client = Vultr(api_key)
        self.account = {}
        self.bandwidth = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Use the data from Vultr API."""
        try:
            self.account = self.client.get_account_info()
            self.bandwidth = self.client.get_account_bandwidth_info()
        except RequestException as exp:
            _LOGGER.error("Error on receive last Vultr data: %s", exp)
