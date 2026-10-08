"""Support for the Netatmo camera siren."""

import logging
from typing import Any, override

from pyatmo import modules as NaModules

from homeassistant.components.siren import SirenEntity, SirenEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_URL_SECURITY,
    NETATMO_CREATE_CAMERA_SIREN,
)
from .coordinator import HOME, SIGNAL_NAME, NetatmoDevice
from .entity import NetatmoModuleEntity
from .web_auth import NetatmoWebSessionAuth

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netatmo camera siren platform."""

    @callback
    def _create_entity(netatmo_device: NetatmoDevice) -> None:
        if not hasattr(netatmo_device.device, "siren_status"):
            return

        entity = NetatmoCameraSiren(netatmo_device)
        _LOGGER.debug("Adding camera siren %s", entity)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_CAMERA_SIREN, _create_entity)
    )


class NetatmoCameraSiren(NetatmoModuleEntity, SirenEntity):
    """Representation of a Netatmo Outdoor Camera siren."""

    device: NaModules.NOC
    _attr_name = None
    _attr_configuration_url = CONF_URL_SECURITY
    _attr_has_entity_name = True
    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF

    def __init__(self, netatmo_device: NetatmoDevice) -> None:
        """Initialize a Netatmo Outdoor Camera siren."""
        super().__init__(netatmo_device)
        self._attr_unique_id = f"{self.device.entity_id}-siren"  # pylint: disable=home-assistant-entity-unique-id-redundant-platform

        self._signal_name = f"{HOME}-{self.home.entity_id}"
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if the camera is powered (alim_status known)."""
        return self.device.alim_status is not None

    def _get_web_auth(self) -> NetatmoWebSessionAuth | None:
        """Get the web session auth if configured."""
        return getattr(self.data_handler, "web_auth", None)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn camera siren on."""
        _LOGGER.debug("Turn camera siren '%s' on", self.name)
        web_auth = self._get_web_auth()
        if not web_auth:
            raise HomeAssistantError(
                "Siren credentials not configured. "
                "Please configure them in integration options."
            )
        result = await web_auth.async_siren_on(
            self.home.entity_id, self.device.entity_id
        )
        if result:
            self._attr_is_on = True
            self.async_write_ha_state()
        else:
            raise HomeAssistantError("Siren command failed.")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn camera siren off."""
        _LOGGER.debug("Turn camera siren '%s' off", self.name)
        web_auth = self._get_web_auth()
        if not web_auth:
            raise HomeAssistantError(
                "Siren credentials not configured. "
                "Please configure them in integration options."
            )
        result = await web_auth.async_siren_off(
            self.home.entity_id, self.device.entity_id
        )
        if result:
            self._attr_is_on = False
            self.async_write_ha_state()
        else:
            raise HomeAssistantError("Siren command failed.")

    @callback
    @override
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._attr_is_on = self.device.siren_status == "sound"
