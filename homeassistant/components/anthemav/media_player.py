"""Support for Anthem Network Receivers and Processors."""
from __future__ import annotations

import logging
from typing import Any

from anthemav.connection import Connection
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.repairs import IssueSeverity, async_create_issue
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ANTHEMAV_UDATE_SIGNAL,
    CONF_MODEL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up our socket to the AVR."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2022.10.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )
    _LOGGER.warning(
        "Configuration of the Anthem A/V Receivers integration in YAML is "
        "deprecated and will be removed in Home Assistant 2022.10; Your "
        "existing configuration has been imported into the UI automatically "
        "and can be safely removed from your configuration.yaml file"
    )
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    name = config_entry.data[CONF_NAME]
    macaddress = config_entry.data[CONF_MAC]
    model = config_entry.data[CONF_MODEL]

    avr = hass.data[DOMAIN][config_entry.entry_id]

    device = AnthemAVR(avr, name, macaddress, model)

    _LOGGER.debug("dump_devicedata: %s", device.dump_avrdata)
    _LOGGER.debug("dump_conndata: %s", avr.dump_conndata)

    async_add_entities([device])


class AnthemAVR(MediaPlayerEntity):
    """Entity reading values from Anthem AVR protocol."""

    _attr_should_poll = False
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, avr: Connection, name: str, macaddress: str, model: str) -> None:
        """Initialize entity with transport."""
        super().__init__()
        self.avr = avr
        self._attr_name = name
        self._attr_unique_id = macaddress
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, macaddress)},
            name=name,
            manufacturer=MANUFACTURER,
            model=model,
        )

    def _lookup(self, propname: str, dval: Any | None = None) -> Any | None:
        return getattr(self.avr.protocol, propname, dval)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{ANTHEMAV_UDATE_SIGNAL}_{self._attr_name}",
                self.async_write_ha_state,
            )
        )

    @property
    def state(self) -> str | None:
        """Return state of power on/off."""
        pwrstate = self._lookup("power")

        if pwrstate is True:
            return STATE_ON
        if pwrstate is False:
            return STATE_OFF
        return None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean reflecting mute state on device."""
        return self._lookup("mute", False)

    @property
    def volume_level(self) -> float | None:
        """Return volume level from 0 to 1."""
        return self._lookup("volume_as_percentage", 0.0)

    @property
    def media_title(self) -> str | None:
        """Return current input name (closest we have to media title)."""
        return self._lookup("input_name", "No Source")

    @property
    def app_name(self) -> str | None:
        """Return details about current video and audio stream."""
        return (
            f"{self._lookup('video_input_resolution_text', '')} "
            f"{self._lookup('audio_input_name', '')}"
        )

    @property
    def source(self) -> str | None:
        """Return currently selected input."""
        return self._lookup("input_name", "Unknown")

    @property
    def source_list(self) -> list[str] | None:
        """Return all active, configured inputs."""
        return self._lookup("input_list", ["Unknown"])

    async def async_select_source(self, source: str) -> None:
        """Change AVR to the designated source (by name)."""
        self._update_avr("input_name", source)

    async def async_turn_off(self) -> None:
        """Turn AVR power off."""
        self._update_avr("power", False)

    async def async_turn_on(self) -> None:
        """Turn AVR power on."""
        self._update_avr("power", True)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set AVR volume (0 to 1)."""
        self._update_avr("volume_as_percentage", volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Engage AVR mute."""
        self._update_avr("mute", mute)

    def _update_avr(self, propname: str, value: Any | None) -> None:
        """Update a property in the AVR."""
        _LOGGER.debug("Sending command to AVR: set %s to %s", propname, str(value))
        setattr(self.avr.protocol, propname, value)

    @property
    def dump_avrdata(self):
        """Return state of avr object for debugging forensics."""
        attrs = vars(self)
        items_string = ", ".join(f"{item}: {item}" for item in attrs.items())
        return f"dump_avrdata: {items_string}"
