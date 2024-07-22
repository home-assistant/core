"""Support for One-Time Password (OTP)."""

from __future__ import annotations

import time

import pyotp
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, CONF_TOKEN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from .const import DEFAULT_NAME, DOMAIN

TIME_STEP = 30  # Default time step assumed by Google Authenticator


PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the OTP sensor."""
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        breaks_in_ha_version="2025.1.0",
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "One-Time Password (OTP)",
        },
    )
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the OTP sensor."""

    async_add_entities(
        [TOTPSensor(entry.data[CONF_NAME], entry.data[CONF_TOKEN], entry.entry_id)],
        True,
    )


# Only TOTP supported at the moment, HOTP might be added later
class TOTPSensor(SensorEntity):
    """Representation of a TOTP sensor."""

    _attr_translation_key = "token"
    _attr_should_poll = False
    _attr_native_value: StateType = None
    _next_expiration: float | None = None
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, name: str, token: str, entry_id: str) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = entry_id
        self._otp = pyotp.TOTP(token)

        self.device_info = DeviceInfo(
            name=name,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
        )

    async def async_added_to_hass(self) -> None:
        """Handle when an entity is about to be added to Home Assistant."""
        self._call_loop()

    @callback
    def _call_loop(self) -> None:
        self._attr_native_value = self._otp.now()
        self.async_write_ha_state()

        # Update must occur at even TIME_STEP, e.g. 12:00:00, 12:00:30,
        # 12:01:00, etc. in order to have synced time (see RFC6238)
        self._next_expiration = TIME_STEP - (time.time() % TIME_STEP)
        self.hass.loop.call_later(self._next_expiration, self._call_loop)
