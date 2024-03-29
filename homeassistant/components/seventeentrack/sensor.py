"""Support for package tracking sensors from 17track.net."""

from __future__ import annotations

import logging

from py17track.errors import SeventeenTrackError
from py17track.package import Package
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_LOCATION,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, entity, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.util import Throttle, slugify

from .const import (
    ATTR_DESTINATION_COUNTRY,
    ATTR_INFO_TEXT,
    ATTR_ORIGIN_COUNTRY,
    ATTR_PACKAGE_TYPE,
    ATTR_PACKAGES,
    ATTR_STATUS,
    ATTR_TIMESTAMP,
    ATTR_TRACKING_INFO_LANGUAGE,
    ATTR_TRACKING_NUMBER,
    ATTRIBUTION,
    CONF_SHOW_ARCHIVED,
    CONF_SHOW_DELIVERED,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENTITY_ID_TEMPLATE,
    NOTIFICATION_DELIVERED_MESSAGE,
    NOTIFICATION_DELIVERED_TITLE,
    UNIQUE_ID_TEMPLATE,
    VALUE_DELIVERED,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SHOW_ARCHIVED, default=False): cv.boolean,
        vol.Optional(CONF_SHOW_DELIVERED, default=False): cv.boolean,
    }
)

ISSUE_PLACEHOLDER = {"url": "/config/integrations/dashboard/add?domain=seventeentrack"}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Initialize 17Track import from config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result["type"] == FlowResultType.CREATE_ENTRY
        or result["reason"] == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            breaks_in_ha_version="2024.10.0",
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "17Track",
            },
        )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version="2024.10.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
            translation_placeholders=ISSUE_PLACEHOLDER,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a 17Track sensor entry."""

    client = hass.data[DOMAIN][config_entry.entry_id]

    data = SeventeenTrackData(
        client,
        async_add_entities,
        DEFAULT_SCAN_INTERVAL,
        config_entry.options[CONF_SHOW_ARCHIVED],
        config_entry.options[CONF_SHOW_DELIVERED],
        str(hass.config.time_zone),
    )
    await data.async_update()


class SeventeenTrackSummarySensor(SensorEntity):
    """Define a summary sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:package"
    _attr_native_unit_of_measurement = "packages"

    def __init__(self, data, status, initial_state) -> None:
        """Initialize."""
        self._attr_extra_state_attributes = {}
        self._data = data
        self._state = initial_state
        self._status = status
        self._attr_name = f"Seventeentrack Packages {status}"
        self._attr_unique_id = f"summary_{data.account_id}_{slugify(status)}"

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self._state is not None

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self._state

    async def async_update(self) -> None:
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
                    ATTR_TIMESTAMP: package.timestamp,
                    ATTR_STATUS: package.status,
                    ATTR_LOCATION: package.location,
                    ATTR_TRACKING_NUMBER: package.tracking_number,
                }
            )

        self._attr_extra_state_attributes[ATTR_PACKAGES] = (
            package_data if package_data else None
        )

        self._state = self._data.summary.get(self._status)


class SeventeenTrackPackageSensor(SensorEntity):
    """Define an individual package sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:package"

    def __init__(self, data, package) -> None:
        """Initialize."""
        self._attr_extra_state_attributes = {
            ATTR_DESTINATION_COUNTRY: package.destination_country,
            ATTR_INFO_TEXT: package.info_text,
            ATTR_TIMESTAMP: package.timestamp,
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
        self._attr_unique_id = UNIQUE_ID_TEMPLATE.format(
            data.account_id, self._tracking_number
        )

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self._data.packages.get(self._tracking_number) is not None

    @property
    def name(self) -> str:
        """Return the name."""
        if not (name := self._friendly_name):
            name = self._tracking_number
        return f"Seventeentrack Package: {name}"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self._state

    async def async_update(self) -> None:
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

        self._attr_extra_state_attributes.update(
            {
                ATTR_INFO_TEXT: package.info_text,
                ATTR_TIMESTAMP: package.timestamp,
                ATTR_LOCATION: package.location,
            }
        )
        self._state = package.status
        self._friendly_name = package.friendly_name

    async def _remove(self, *_):
        """Remove entity itself."""
        await self.async_remove(force_remove=True)

        reg = er.async_get(self.hass)
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

        persistent_notification.create(
            self.hass, message, title=title, notification_id=notification_id
        )


class SeventeenTrackData:
    """Define a data handler for 17track.net."""

    def __init__(
        self,
        client,
        async_add_entities,
        scan_interval,
        show_archived,
        show_delivered,
        timezone,
    ) -> None:
        """Initialize."""
        self._async_add_entities = async_add_entities
        self._client = client
        self._scan_interval = scan_interval
        self._show_archived = show_archived
        self.account_id = client.profile.account_id
        self.packages: dict[str, Package] = {}
        self.show_delivered = show_delivered
        self.timezone = timezone
        self.summary: dict[str, int] = {}
        self.async_update = Throttle(self._scan_interval)(self._async_update)
        self.first_update = True

    async def _async_update(self):
        """Get updated data from 17track.net."""
        entities: list[entity.Entity] = []

        try:
            packages = await self._client.profile.packages(
                show_archived=self._show_archived, tz=self.timezone
            )
            _LOGGER.debug("New package data received: %s", packages)

            new_packages = {p.tracking_number: p for p in packages}

            to_add = set(new_packages) - set(self.packages)

            _LOGGER.debug("Will add new tracking numbers: %s", to_add)
            if to_add:
                entities.extend(
                    SeventeenTrackPackageSensor(self, new_packages[tracking_number])
                    for tracking_number in to_add
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
                entities.extend(
                    SeventeenTrackSummarySensor(self, status, quantity)
                    for status, quantity in self.summary.items()
                )

        except SeventeenTrackError as err:
            _LOGGER.error("There was an error retrieving the summary: %s", err)
            self.summary = {}

        self._async_add_entities(entities, True)
