"""Base entity for the Whirlpool integration."""

import logging
from typing import override

from whirlpool.appliance import Appliance
from whirlpool.oven import Cavity as OvenCavity, Oven

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class WhirlpoolEntity(Entity):
    """Base class for Whirlpool entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _unavailable_logged: bool = False

    def __init__(self, appliance: Appliance, unique_id_suffix: str = "") -> None:
        """Initialize the entity."""
        self._appliance = appliance

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, appliance.said)},
            name=appliance.name.capitalize() if appliance.name else appliance.said,
            manufacturer="Whirlpool",
            model_id=appliance.appliance_info.model_number,
        )
        self._attr_unique_id = f"{appliance.said}{unique_id_suffix}"

    @override
    async def async_added_to_hass(self) -> None:
        """Register attribute updates callback."""
        self._appliance.register_attr_callback(self._async_attr_callback)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unregister attribute updates callback."""
        self._appliance.unregister_attr_callback(self._async_attr_callback)

    @callback
    def _async_attr_callback(self) -> None:
        _LOGGER.debug("Attribute update for entity %s", self.entity_id)
        self._attr_available = self._appliance.get_online()

        if not self._attr_available:
            if not self._unavailable_logged:
                _LOGGER.info("The entity %s is unavailable", self.entity_id)
                self._unavailable_logged = True
        elif self._unavailable_logged:
            _LOGGER.info("The entity %s is back online", self.entity_id)
            self._unavailable_logged = False

        self.async_write_ha_state()

    @staticmethod
    def _check_service_request(result: bool) -> None:
        """Check result of a request and raise HomeAssistantError if it failed."""
        if not result:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="request_failed",
            )


class WhirlpoolOvenEntity(WhirlpoolEntity):
    """Base class for Whirlpool oven entities."""

    _appliance: Oven

    @staticmethod
    def cavity_suffix(oven: Oven, cavity: OvenCavity) -> str:
        """Return the unique-id and translation-key suffix for an oven cavity."""
        if oven.get_oven_cavity_exists(
            OvenCavity.Upper
        ) and oven.get_oven_cavity_exists(OvenCavity.Lower):
            return "_upper" if cavity == OvenCavity.Upper else "_lower"
        return ""

    def __init__(
        self,
        appliance: Oven,
        cavity: OvenCavity,
        translation_key_base: str | None,
        unique_id_suffix: str = "",
    ) -> None:
        """Initialize the entity."""
        self.cavity = cavity
        cavity_suffix = self.cavity_suffix(appliance, cavity)
        super().__init__(
            appliance, unique_id_suffix=f"{unique_id_suffix}{cavity_suffix}"
        )
        self._attr_translation_key = f"{translation_key_base}{cavity_suffix}"
