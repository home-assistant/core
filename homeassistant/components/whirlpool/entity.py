"""Base entity for the Whirlpool integration."""

from whirlpool.appliance import Appliance
from whirlpool.oven import Cavity as OvenCavity, Oven

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class WhirlpoolEntity(Entity):
    """Base class for Whirlpool entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

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

    async def async_added_to_hass(self) -> None:
        """Register attribute updates callback."""
        self._appliance.register_attr_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister attribute updates callback."""
        self._appliance.unregister_attr_callback(self.async_write_ha_state)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._appliance.get_online()

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

    def __init__(
        self,
        appliance: Oven,
        cavity: OvenCavity,
        translation_key_base: str,
        unique_id_suffix: str = "",
    ) -> None:
        """Initialize the entity."""
        self.cavity = cavity
        cavity_suffix = ""
        if (
            sum(1 for cavity in OvenCavity if appliance.get_oven_cavity_exists(cavity))
            > 1
        ):
            if cavity == OvenCavity.Upper:
                cavity_suffix = "_upper"
            elif cavity == OvenCavity.Lower:
                cavity_suffix = "_lower"
        super().__init__(
            appliance, unique_id_suffix=f"{unique_id_suffix}{cavity_suffix}"
        )
        self._attr_translation_key = f"{translation_key_base}{cavity_suffix}"
