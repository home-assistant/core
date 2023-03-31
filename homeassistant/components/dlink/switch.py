"""Support for D-Link Power Plug Switches."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_TOTAL_CONSUMPTION,
    CONF_USE_LEGACY_PROTOCOL,
    DEFAULT_NAME,
    DEFAULT_USERNAME,
    DOMAIN,
)
from .entity import DLinkEntity

SCAN_INTERVAL = timedelta(minutes=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD, default=""): cv.string,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_USE_LEGACY_PROTOCOL, default=False): cv.boolean,
    }
)

SWITCH_TYPE = SwitchEntityDescription(
    key="switch",
    name="Switch",
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a D-Link Smart Plug."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.4.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the D-Link Power Plug switch."""
    async_add_entities(
        [SmartPlugSwitch(entry, hass.data[DOMAIN][entry.entry_id], SWITCH_TYPE)],
        True,
    )


class SmartPlugSwitch(DLinkEntity, SwitchEntity):
    """Representation of a D-Link Smart Plug switch."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the device."""
        try:
            temperature = self.hass.config.units.temperature(
                int(self.data.temperature), UnitOfTemperature.CELSIUS
            )
        except ValueError:
            temperature = None

        try:
            total_consumption = float(self.data.total_consumption)
        except ValueError:
            total_consumption = None

        attrs = {
            ATTR_TOTAL_CONSUMPTION: total_consumption,
            ATTR_TEMPERATURE: temperature,
        }

        return attrs

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.data.state == "ON"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.data.smartplug.state = "ON"

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.data.smartplug.state = "OFF"

    def update(self) -> None:
        """Get the latest data from the smart plug and updates the states."""
        self.data.update()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.data.available
