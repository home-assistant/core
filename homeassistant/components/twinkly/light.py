"""The Twinkly light component."""

import logging
from typing import Any, Dict, Optional

from aiohttp import ClientError
from twinkly_client import TwinklyClient
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_validation import string
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTR_HOST,
    CONF_ENTRY_HOST,
    CONF_ENTRY_ID,
    CONF_ENTRY_MODEL,
    CONF_ENTRY_NAME,
    DEV_MODEL,
    DEV_NAME,
    DOMAIN,
    HIDDEN_DEV_VALUES,
)

_LOGGER = logging.getLogger(__name__)

# Schema for configuration.yaml
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): string,
        vol.Optional(CONF_NAME): string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setups eneity from the configuration.yaml."""
    host = config[CONF_HOST]
    name = config.get(CONF_NAME)

    client = TwinklyClient(host, async_get_clientsession(hass))
    entity = TwinklyLight(None, client, name, None)

    async_add_entities([entity], True)

    return True


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Setups an entity from a config entry (UI config flow)."""
    uuid = config_entry.data[CONF_ENTRY_ID]
    host = config_entry.data[CONF_ENTRY_HOST]
    name = config_entry.data[CONF_ENTRY_NAME]
    model = config_entry.data[CONF_ENTRY_MODEL]

    client = TwinklyClient(host, async_get_clientsession(hass))
    entity = TwinklyLight(uuid, client, name, model)

    # We make sure the device is up-to-date before adding the entity to HA
    await entity.async_update()

    async_add_entities([entity])


class TwinklyLight(LightEntity):
    """Implementation of the light for the Twinkly service."""

    def __init__(self, uuid: str, client: TwinklyClient, name: str, model: str):
        """Initialize a TwinklyLight entity."""
        self._id = uuid
        self._client = client

        # Those are saved in the config entry in order to have meaningful values even
        # if the device is currently offline.
        # They are expected to be overridden by the device_info.
        self.__name = name
        self.__model = model

        # Set default state before any update
        self._is_on = False
        self._brightness = 0
        self._is_available = False
        self._attributes = {ATTR_HOST: client.host}

    @property
    def supported_features(self):
        """Get the features supported by this entity."""
        return SUPPORT_BRIGHTNESS

    @property
    def should_poll(self) -> bool:
        """Get a boolean which indicates if this entity should be polled."""
        return True

    @property
    def available(self) -> bool:
        """Get a boolean which indicates if this entity is currently available."""
        return self._is_available

    @property
    def unique_id(self) -> Optional[str]:
        """Id of the device."""
        return self._id

    @property
    def name(self) -> str:
        """Name of the device."""
        return (
            self._attributes[DEV_NAME]
            if DEV_NAME in self._attributes
            else self.__name
            if self.__name
            else "Twinkly light"
        )

    @property
    def model(self) -> str:
        """Name of the device."""
        return (
            self._attributes[DEV_MODEL]
            if DEV_MODEL in self._attributes
            else self.__model
        )

    @property
    def icon(self) -> str:
        """Icon of the device."""
        return "mdi:string-lights"

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Get device specific attributes."""
        return (
            {
                "identifiers": {(DOMAIN, self._id)},
                "name": self.name,
                "manufacturer": "LEDWORKS",
                "model": self.model,
            }
            if self._id
            else None  # device_info is available only for entities configured from the UI
        )

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._is_on

    @property
    def brightness(self) -> Optional[int]:
        """Return the brightness of the light."""
        return self._brightness

    @property
    def state_attributes(self) -> dict:
        """Return device specific state attributes."""

        attributes = self._attributes

        # Make sure to update any normalized property
        attributes[ATTR_HOST] = self._client.host
        attributes[ATTR_BRIGHTNESS] = self._brightness

        return attributes

    async def async_turn_on(self, **kwargs) -> None:
        """Turn device on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(int(kwargs[ATTR_BRIGHTNESS]) / 2.55)

            # If brightness is 0, the twinkly will only "disable" the brightness,
            # which means that it will be 100%.
            if brightness == 0:
                await self._client.set_is_on(False)
                return

            await self._client.set_brightness(brightness)

        await self._client.set_is_on(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn device off."""
        await self._client.set_is_on(False)

    async def async_update(self) -> None:
        """Asynchronously updates the device properties."""
        _LOGGER.info("Updating '%s'", self._client.host)

        try:
            self._is_on = await self._client.get_is_on()

            self._brightness = (
                (await self._client.get_brigthness()) * 2.55 if self._is_on else 0
            )

            device_info = await self._client.get_device_info()
            for key, value in device_info.items():
                if key not in HIDDEN_DEV_VALUES:
                    self._attributes[key] = value

            if not self._is_available:
                _LOGGER.info("Twinkly '%s' is now available", self._client.host)

            # We don't use the echo API to track the availability since we already have to pull
            # the device to get its state.
            self._is_available = True
        except ClientError:
            # We log this as "info" as it's pretty common that the christmas light are not reachable in july
            if self._is_available:
                _LOGGER.info("Twinkly '%s' is not reachable", self._client.host)

            self._is_available = False
