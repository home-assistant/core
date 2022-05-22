"""Platform for the Aladdin Connect cover component."""
from __future__ import annotations

import logging
from typing import Any, Final

from aladdin_connect import AladdinConnectClient
import voluptuous as vol

from homeassistant.components.cover import (
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    CoverDeviceClass,
    CoverEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, STATES_MAP, SUPPORTED_FEATURES
from .model import DoorDevice

_LOGGER: Final = logging.getLogger(__name__)

PLATFORM_SCHEMA: Final = BASE_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Aladdin Connect devices yaml depreciated."""
    _LOGGER.warning(
        "Configuring Aladdin Connect through yaml is deprecated"
        "Please remove it from your configuration as it has already been imported to a config entry"
    )
    await hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aladdin Connect platform."""
    acc = hass.data[DOMAIN][config_entry.entry_id]
    try:
        doors = await hass.async_add_executor_job(acc.get_doors)

    except (TypeError, KeyError, NameError, ValueError) as ex:
        _LOGGER.error("%s", ex)
        raise ConfigEntryNotReady from ex

    async_add_entities(
        (AladdinDevice(acc, door) for door in doors),
        update_before_add=True,
    )


class AladdinDevice(CoverEntity):
    """Representation of Aladdin Connect cover."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = SUPPORTED_FEATURES

    def __init__(self, acc: AladdinConnectClient, device: DoorDevice) -> None:
        """Initialize the Aladdin Connect cover."""
        self._acc = acc
        self._device_id = device["device_id"]
        self._number = device["door_number"]
        self._attr_name = device["name"]
        self._attr_unique_id = f"{self._device_id}-{self._number}"

    def close_cover(self, **kwargs: Any) -> None:
        """Issue close command to cover."""
        self._acc.close_door(self._device_id, self._number)

    def open_cover(self, **kwargs: Any) -> None:
        """Issue open command to cover."""
        self._acc.open_door(self._device_id, self._number)

    def update(self) -> None:
        """Update status of cover."""
        status = STATES_MAP.get(
            self._acc.get_door_status(self._device_id, self._number)
        )
        self._attr_is_opening = status == STATE_OPENING
        self._attr_is_closing = status == STATE_CLOSING
        self._attr_is_closed = None if status is None else status == STATE_CLOSED
