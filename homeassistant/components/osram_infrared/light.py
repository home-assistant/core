"""Light platform for Osram IR integration."""

from dataclasses import dataclass

from homeassistant.components.infrared import InfraredEmitterConsumerEntity

# do later: Add protocol here
# from infrared_protocols.codes.osram.light
from homeassistant.components.light import LightEntity, LightEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INFRARED_ENTITY_ID
from .entity import OsramIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OsramIrLightEntityDescription(LightEntityDescription):
    """Describes Osram IR light entity."""

    # do later: Add command_code here
    # command_code: OsramLightCode


OSRAM_LIGHT_DESCRIPTIONS: tuple[OsramIrLightEntityDescription, ...] = (
    # OsramIrLightEntityDescription(
    #    key="power_on", translation_key="power_on", command_code=OsramLightCode.POWER_ON
    # ),
    # OsramIrLightEntityDescription(
    #    key="power_off", translation_key="power_off", command_code=OsramLightCode.POWER_OFF
    # ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Osram IR light from config entry."""
    if not (infrared_entity_id := entry.data.get(CONF_INFRARED_ENTITY_ID)):
        return

    async_add_entities(
        OsramIrLight(entry, infrared_entity_id, description)
        for description in OSRAM_LIGHT_DESCRIPTIONS
    )


class OsramIrLight(OsramIrEntity, InfraredEmitterConsumerEntity, LightEntity):
    """Osram IR light entity."""

    entity_description: OsramIrLightEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        infrared_entity_id: str,
        description: OsramIrLightEntityDescription,
    ) -> None:
        """Initialize Osram IR light."""
        super().__init__(entry, unique_id_suffix=description.key)
        self._infrared_emitter_entity_id = infrared_entity_id
        self.entity_description = description

    # async def async_toggle(self, **kwargs: Any) -> None:
    #    """Toggle the entity."""
    #    if not self.is_on:
    # await self._send_command(OSRAM_LIGHT_DESCRIPTIONS)
    #        return

    # params = process_turn_off_params(self.hass, self, kwargs)
    # await self.async_turn_off(**filter_turn_off_params(self, params))
