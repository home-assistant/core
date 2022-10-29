"""
Support for Fido.

Get data from 'Usage Summary' page:
https://www.fido.ca/pages/#/my-account/wireless
"""
from __future__ import annotations

from datetime import timedelta
import logging

from pyfido import FidoClient
from pyfido.client import PyFidoError
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    DATA_KILOBITS,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

PRICE = "CAD"
MESSAGES = "messages"

DEFAULT_NAME = "Fido"

REQUESTS_TIMEOUT = 15
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="fido_dollar",
        name="Fido dollar",
        native_unit_of_measurement=PRICE,
        icon="mdi:cash",
    ),
    SensorEntityDescription(
        key="balance",
        name="Balance",
        native_unit_of_measurement=PRICE,
        icon="mdi:cash",
    ),
    SensorEntityDescription(
        key="data_used",
        name="Data used",
        native_unit_of_measurement=DATA_KILOBITS,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="data_limit",
        name="Data limit",
        native_unit_of_measurement=DATA_KILOBITS,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="data_remaining",
        name="Data remaining",
        native_unit_of_measurement=DATA_KILOBITS,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="text_used",
        name="Text used",
        native_unit_of_measurement=MESSAGES,
        icon="mdi:message-text",
    ),
    SensorEntityDescription(
        key="text_limit",
        name="Text limit",
        native_unit_of_measurement=MESSAGES,
        icon="mdi:message-text",
    ),
    SensorEntityDescription(
        key="text_remaining",
        name="Text remaining",
        native_unit_of_measurement=MESSAGES,
        icon="mdi:message-text",
    ),
    SensorEntityDescription(
        key="mms_used",
        name="MMS used",
        native_unit_of_measurement=MESSAGES,
        icon="mdi:message-image",
    ),
    SensorEntityDescription(
        key="mms_limit",
        name="MMS limit",
        native_unit_of_measurement=MESSAGES,
        icon="mdi:message-image",
    ),
    SensorEntityDescription(
        key="mms_remaining",
        name="MMS remaining",
        native_unit_of_measurement=MESSAGES,
        icon="mdi:message-image",
    ),
    SensorEntityDescription(
        key="text_int_used",
        name="International text used",
        native_unit_of_measurement=MESSAGES,
        icon="mdi:message-alert",
    ),
    SensorEntityDescription(
        key="text_int_limit",
        name="International text limit",
        native_unit_of_measurement=MESSAGES,
        icon="mdi:message-alert",
    ),
    SensorEntityDescription(
        key="text_int_remaining",
        name="International remaining",
        native_unit_of_measurement=MESSAGES,
        icon="mdi:message-alert",
    ),
    SensorEntityDescription(
        key="talk_used",
        name="Talk used",
        native_unit_of_measurement=TIME_MINUTES,
        icon="mdi:cellphone",
    ),
    SensorEntityDescription(
        key="talk_limit",
        name="Talk limit",
        native_unit_of_measurement=TIME_MINUTES,
        icon="mdi:cellphone",
    ),
    SensorEntityDescription(
        key="talk_remaining",
        name="Talk remaining",
        native_unit_of_measurement=TIME_MINUTES,
        icon="mdi:cellphone",
    ),
    SensorEntityDescription(
        key="other_talk_used",
        name="Other Talk used",
        native_unit_of_measurement=TIME_MINUTES,
        icon="mdi:cellphone",
    ),
    SensorEntityDescription(
        key="other_talk_limit",
        name="Other Talk limit",
        native_unit_of_measurement=TIME_MINUTES,
        icon="mdi:cellphone",
    ),
    SensorEntityDescription(
        key="other_talk_remaining",
        name="Other Talk remaining",
        native_unit_of_measurement=TIME_MINUTES,
        icon="mdi:cellphone",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_VARIABLES): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Fido sensor."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    httpsession = async_get_clientsession(hass)
    fido_data = FidoData(username, password, httpsession)
    ret = await fido_data.async_update()
    if ret is False:
        return

    name = config[CONF_NAME]
    monitored_variables = config[CONF_MONITORED_VARIABLES]
    entities = [
        FidoSensor(fido_data, name, number, description)
        for number in fido_data.client.get_phone_numbers()
        for description in SENSOR_TYPES
        if description.key in monitored_variables
    ]

    async_add_entities(entities, True)


class FidoSensor(SensorEntity):
    """Implementation of a Fido sensor."""

    def __init__(self, fido_data, name, number, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self.fido_data = fido_data
        self._number = number

        self._attr_name = f"{name} {number} {description.name}"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {"number": self._number}

    async def async_update(self) -> None:
        """Get the latest data from Fido and update the state."""
        await self.fido_data.async_update()
        if (sensor_type := self.entity_description.key) == "balance":
            if self.fido_data.data.get(sensor_type) is not None:
                self._attr_native_value = round(self.fido_data.data[sensor_type], 2)
        else:
            if self.fido_data.data.get(self._number, {}).get(sensor_type) is not None:
                self._attr_native_value = round(
                    self.fido_data.data[self._number][sensor_type], 2
                )


class FidoData:
    """Get data from Fido."""

    def __init__(self, username, password, httpsession):
        """Initialize the data object."""

        self.client = FidoClient(username, password, REQUESTS_TIMEOUT, httpsession)
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from Fido."""

        try:
            await self.client.fetch_data()
        except PyFidoError as exp:
            _LOGGER.error("Error on receive last Fido data: %s", exp)
            return False
        # Update data
        self.data = self.client.get_data()
        return True
