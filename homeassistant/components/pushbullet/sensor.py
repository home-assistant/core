"""Pushbullet platform for sensor component."""
from __future__ import annotations

import logging
import threading

from pushbullet import InvalidKeyError, Listener, PushBullet
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_API_KEY, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="application_name",
        name="Application name",
    ),
    SensorEntityDescription(
        key="body",
        name="Body",
    ),
    SensorEntityDescription(
        key="notification_id",
        name="Notification ID",
    ),
    SensorEntityDescription(
        key="notification_tag",
        name="Notification tag",
    ),
    SensorEntityDescription(
        key="package_name",
        name="Package name",
    ),
    SensorEntityDescription(
        key="receiver_email",
        name="Receiver email",
    ),
    SensorEntityDescription(
        key="sender_email",
        name="Sender email",
    ),
    SensorEntityDescription(
        key="source_device_iden",
        name="Sender device ID",
    ),
    SensorEntityDescription(
        key="title",
        name="Title",
    ),
    SensorEntityDescription(
        key="type",
        name="Type",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["title", "body"]): vol.All(
            cv.ensure_list, vol.Length(min=1), [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Pushbullet Sensor platform."""

    try:
        pushbullet = PushBullet(config.get(CONF_API_KEY))
    except InvalidKeyError:
        _LOGGER.error("Wrong API key for Pushbullet supplied")
        return

    pbprovider = PushBulletNotificationProvider(pushbullet)

    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    entities = [
        PushBulletNotificationSensor(pbprovider, description)
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]
    add_entities(entities)


class PushBulletNotificationSensor(SensorEntity):
    """Representation of a Pushbullet Sensor."""

    def __init__(
        self,
        pb,  # pylint: disable=invalid-name
        description: SensorEntityDescription,
    ):
        """Initialize the Pushbullet sensor."""
        self.entity_description = description
        self.pushbullet = pb

        self._attr_name = f"Pushbullet {description.key}"

    def update(self) -> None:
        """Fetch the latest data from the sensor.

        This will fetch the 'sensor reading' into self._state but also all
        attributes into self._state_attributes.
        """
        try:
            self._attr_native_value = self.pushbullet.data[self.entity_description.key]
            self._attr_extra_state_attributes = self.pushbullet.data
        except (KeyError, TypeError):
            pass


class PushBulletNotificationProvider:
    """Provider for an account, leading to one or more sensors."""

    def __init__(self, pushbullet):
        """Start to retrieve pushes from the given Pushbullet instance."""

        self.pushbullet = pushbullet
        self._data = None
        self.listener = None
        self.thread = threading.Thread(target=self.retrieve_pushes)
        self.thread.daemon = True
        self.thread.start()

    def on_push(self, data):
        """Update the current data.

        Currently only monitors pushes but might be extended to monitor
        different kinds of Pushbullet events.
        """
        if data["type"] == "push":
            self._data = data["push"]

    @property
    def data(self):
        """Return the current data stored in the provider."""
        return self._data

    def retrieve_pushes(self):
        """Retrieve_pushes.

        Spawn a new Listener and links it to self.on_push.
        """

        self.listener = Listener(account=self.pushbullet, on_push=self.on_push)
        _LOGGER.debug("Getting pushes")
        try:
            self.listener.run_forever()
        finally:
            self.listener.close()
