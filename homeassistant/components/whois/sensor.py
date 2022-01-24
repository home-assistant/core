"""Get WHOIS information for a given host."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import cast

import voluptuous as vol
import whois
from whois import Domain
from whois.exceptions import (
    FailedParsingWhoisOutput,
    UnknownDateFormat,
    UnknownTld,
    WhoisCommandFailed,
)

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_NAME, TIME_DAYS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_EXPIRES,
    ATTR_NAME_SERVERS,
    ATTR_REGISTRAR,
    ATTR_UPDATED,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
)

SCAN_INTERVAL = timedelta(hours=24)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


@dataclass
class WhoisSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Domain], int | None]


@dataclass
class WhoisSensorEntityDescription(
    SensorEntityDescription, WhoisSensorEntityDescriptionMixin
):
    """Describes a Whois sensor entity."""


def _days_until_expiration(domain: Domain) -> int | None:
    """Calculate days left until domain expires."""
    if domain.expiration_date is None:
        return None
    # We need to cast here, as (unlike Pyright) mypy isn't able to determine the type.
    return cast(int, (domain.expiration_date - domain.expiration_date.utcnow()).days)


SENSORS: tuple[WhoisSensorEntityDescription, ...] = (
    WhoisSensorEntityDescription(
        key="days_until_expiration",
        name="Days Until Expiration",
        icon="mdi:calendar-clock",
        native_unit_of_measurement=TIME_DAYS,
        value_fn=_days_until_expiration,
    ),
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the WHOIS sensor."""
    LOGGER.warning(
        "Configuration of the Whois platform in YAML is deprecated and will be "
        "removed in Home Assistant 2022.4; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_DOMAIN: config[CONF_DOMAIN], CONF_NAME: config[CONF_NAME]},
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    domain = entry.data[CONF_DOMAIN]
    try:
        await hass.async_add_executor_job(whois.query, domain)
    except UnknownTld:
        LOGGER.error("Could not set up whois for %s, TLD is unknown", domain)
        return
    except (FailedParsingWhoisOutput, WhoisCommandFailed, UnknownDateFormat) as ex:
        LOGGER.error("Exception %s occurred during WHOIS lookup for %s", ex, domain)
        return

    async_add_entities(
        [
            WhoisSensorEntity(
                domain=domain,
                description=description,
            )
            for description in SENSORS
        ],
        update_before_add=True,
    )


class WhoisSensorEntity(SensorEntity):
    """Implementation of a WHOIS sensor."""

    entity_description: WhoisSensorEntityDescription

    def __init__(self, description: WhoisSensorEntityDescription, domain: str) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = domain
        self._attr_unique_id = f"{domain}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, domain)},
            entry_type=DeviceEntryType.SERVICE,
        )
        self._domain = domain

    def _empty_value_and_attributes(self) -> None:
        """Empty the state and attributes on an error."""
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    def update(self) -> None:
        """Get the current WHOIS data for the domain."""
        try:
            response: Domain | None = whois.query(self._domain)
        except (FailedParsingWhoisOutput, WhoisCommandFailed, UnknownDateFormat) as ex:
            LOGGER.error("Exception %s occurred during WHOIS lookup", ex)
            self._empty_value_and_attributes()
            return

        if response:
            if not response.expiration_date:
                LOGGER.error("Failed to find expiration_date in whois lookup response")
                self._empty_value_and_attributes()
                return

            self._attr_native_value = self.entity_description.value_fn(response)

            # Only add attributes to the original sensor
            if self.entity_description.key != "days_until_expiration":
                return None

            attrs = {}
            attrs[ATTR_EXPIRES] = response.expiration_date.isoformat()

            if response.name_servers:
                attrs[ATTR_NAME_SERVERS] = " ".join(response.name_servers)

            if response.last_updated:
                attrs[ATTR_UPDATED] = response.last_updated.isoformat()

            if response.registrar:
                attrs[ATTR_REGISTRAR] = response.registrar

            self._attr_extra_state_attributes = attrs
