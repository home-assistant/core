"""Support for package tracking sensors from 17track.net."""
from datetime import timedelta
import logging

from py17track import Client as SeventeenTrackClient
from py17track.errors import SeventeenTrackError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LOCATION,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later
from homeassistant.util import Throttle, slugify

_LOGGER = logging.getLogger(__name__)

ATTR_DESTINATION_COUNTRY = "destination_country"
ATTR_FRIENDLY_NAME = "friendly_name"
ATTR_INFO_TEXT = "info_text"
ATTR_ORIGIN_COUNTRY = "origin_country"
ATTR_PACKAGES = "packages"
ATTR_PACKAGE_TYPE = "package_type"
ATTR_STATUS = "status"
ATTR_TRACKING_INFO_LANGUAGE = "tracking_info_language"
ATTR_TRACKING_NUMBER = "tracking_number"

CONF_SHOW_ARCHIVED = "show_archived"
CONF_SHOW_DELIVERED = "show_delivered"

DATA_PACKAGES = "package_data"
DATA_SUMMARY = "summary_data"

DEFAULT_ATTRIBUTION = "Data provided by 17track.net"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

UNIQUE_ID_TEMPLATE = "package_{0}_{1}"
ENTITY_ID_TEMPLATE = "sensor.seventeentrack_package_{0}"

NOTIFICATION_DELIVERED_ID = "package_delivered_{0}"
NOTIFICATION_DELIVERED_TITLE = "Package {0} delivered"
NOTIFICATION_DELIVERED_MESSAGE = (
    "Package Delivered: {0}<br />Visit 17.track for more information: "
    "https://t.17track.net/track#nums={1}"
)

VALUE_DELIVERED = "Delivered"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SHOW_ARCHIVED, default=False): cv.boolean,
        vol.Optional(CONF_SHOW_DELIVERED, default=False): cv.boolean,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Configure the platform and add the sensors."""

    websession = aiohttp_client.async_get_clientsession(hass)

    client = SeventeenTrackClient(websession)

    try:
        login_result = await client.profile.login(
            config[CONF_USERNAME], config[CONF_PASSWORD]
        )

        if not login_result:
            _LOGGER.error("Invalid username and password provided")
            return
    except SeventeenTrackError as err:
        _LOGGER.error("There was an error while logging in: %s", err)
        return

    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    data = SeventeenTrackData(
        client,
        async_add_entities,
        scan_interval,
        config[CONF_SHOW_ARCHIVED],
        config[CONF_SHOW_DELIVERED],
    )
    await data.async_update()


class SeventeenTrackSummarySensor(Entity):
    """Define a summary sensor."""

    def __init__(self, data, status, initial_state):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._data = data
        self._state = initial_state
        self._status = status

    @property
    def available(self):
        """Return whether the entity is available."""
        return self._state is not None

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:package"

    @property
    def name(self):
        """Return the name."""
        return f"Seventeentrack Packages {self._status}"

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return "summary_{}_{}".format(self._data.account_id, slugify(self._status))

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return "packages"

    async def async_update(self):
        """Update the sensor."""
        await self._data.async_update()

        package_data = []
        for package in self._data.packages.values():
            if package.status != self._status:
                continue

            package_data.append(
                {
                    ATTR_FRIENDLY_NAME: package.friendly_name,
                    ATTR_INFO_TEXT: package.info_text,
                    ATTR_STATUS: package.status,
                    ATTR_LOCATION: package.location,
                    ATTR_TRACKING_NUMBER: package.tracking_number,
                }
            )

        if package_data:
            self._attrs[ATTR_PACKAGES] = package_data

        self._state = self._data.summary.get(self._status)


class SeventeenTrackPackageSensor(Entity):
    """Define an individual package sensor."""

    def __init__(self, data, package):
        """Initialize."""
        self._attrs = {
            ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION,
            ATTR_DESTINATION_COUNTRY: package.destination_country,
            ATTR_INFO_TEXT: package.info_text,
            ATTR_LOCATION: package.location,
            ATTR_ORIGIN_COUNTRY: package.origin_country,
            ATTR_PACKAGE_TYPE: package.package_type,
            ATTR_TRACKING_INFO_LANGUAGE: package.tracking_info_language,
            ATTR_TRACKING_NUMBER: package.tracking_number,
        }
        self._data = data
        self._friendly_name = package.friendly_name
        self._state = package.status
        self._tracking_number = package.tracking_number
        self.entity_id = ENTITY_ID_TEMPLATE.format(self._tracking_number)

    @property
    def available(self):
        """Return whether the entity is available."""
        return self._data.packages.get(self._tracking_number) is not None

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:package"

    @property
    def name(self):
        """Return the name."""
        name = self._friendly_name
        if not name:
            name = self._tracking_number
        return f"Seventeentrack Package: {name}"

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return UNIQUE_ID_TEMPLATE.format(self._data.account_id, self._tracking_number)

    async def async_update(self):
        """Update the sensor."""
        await self._data.async_update()

        if not self.available:
            # Entity cannot be removed while its being added
            async_call_later(self.hass, 1, self._remove)
            return

        package = self._data.packages.get(self._tracking_number, None)

        # If the user has elected to not see delivered packages and one gets
        # delivered, post a notification:
        if package.status == VALUE_DELIVERED and not self._data.show_delivered:
            self._notify_delivered()
            # Entity cannot be removed while its being added
            async_call_later(self.hass, 1, self._remove)
            return

        self._attrs.update(
            {ATTR_INFO_TEXT: package.info_text, ATTR_LOCATION: package.location}
        )
        self._state = package.status
        self._friendly_name = package.friendly_name

    async def _remove(self, *_):
        """Remove entity itself."""
        await self.async_remove()

        reg = await self.hass.helpers.entity_registry.async_get_registry()
        entity_id = reg.async_get_entity_id(
            "sensor",
            "seventeentrack",
            UNIQUE_ID_TEMPLATE.format(self._data.account_id, self._tracking_number),
        )
        if entity_id:
            reg.async_remove(entity_id)

    def _notify_delivered(self):
        """Notify when package is delivered."""
        _LOGGER.info("Package delivered: %s", self._tracking_number)

        identification = (
            self._friendly_name if self._friendly_name else self._tracking_number
        )
        message = NOTIFICATION_DELIVERED_MESSAGE.format(
            identification, self._tracking_number
        )
        title = NOTIFICATION_DELIVERED_TITLE.format(identification)
        notification_id = NOTIFICATION_DELIVERED_TITLE.format(self._tracking_number)

        self.hass.components.persistent_notification.create(
            message, title=title, notification_id=notification_id
        )


class SeventeenTrackData:
    """Define a data handler for 17track.net."""

    def __init__(
        self, client, async_add_entities, scan_interval, show_archived, show_delivered
    ):
        """Initialize."""
        self._async_add_entities = async_add_entities
        self._client = client
        self._scan_interval = scan_interval
        self._show_archived = show_archived
        self.account_id = client.profile.account_id
        self.packages = {}
        self.show_delivered = show_delivered
        self.summary = {}

        self.async_update = Throttle(self._scan_interval)(self._async_update)
        self.first_update = True

    async def _async_update(self):
        """Get updated data from 17track.net."""

        try:
            packages = await self._client.profile.packages(
                show_archived=self._show_archived
            )
            _LOGGER.debug("New package data received: %s", packages)

            new_packages = {p.tracking_number: p for p in packages}

            to_add = set(new_packages) - set(self.packages)

            _LOGGER.debug("Will add new tracking numbers: %s", to_add)
            if to_add:
                self._async_add_entities(
                    [
                        SeventeenTrackPackageSensor(self, new_packages[tracking_number])
                        for tracking_number in to_add
                    ],
                    True,
                )

            self.packages = new_packages
        except SeventeenTrackError as err:
            _LOGGER.error("There was an error retrieving packages: %s", err)

        try:
            self.summary = await self._client.profile.summary(
                show_archived=self._show_archived
            )
            _LOGGER.debug("New summary data received: %s", self.summary)

            # creating summary sensors on first update
            if self.first_update:
                self.first_update = False

                self._async_add_entities(
                    [
                        SeventeenTrackSummarySensor(self, status, quantity)
                        for status, quantity in self.summary.items()
                    ],
                    True,
                )

        except SeventeenTrackError as err:
            _LOGGER.error("There was an error retrieving the summary: %s", err)
            self.summary = {}
