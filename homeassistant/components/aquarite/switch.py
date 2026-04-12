"""Aquarite Switch entities."""
from __future__ import annotations

from dataclasses import dataclass

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .const import DOMAIN
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity


@dataclass(frozen=True)
class AquariteSwitchConfig:
    """Configuration for an Aquarite switch."""

    translation_key: str
    value_path: str
    is_relay: bool = False


SWITCH_DEFINITIONS: tuple[AquariteSwitchConfig, ...] = (
    AquariteSwitchConfig("electrolysis_cover", "hidro.cover_enabled"),
    AquariteSwitchConfig("electrolysis_boost", "hidro.cloration_enabled"),
    AquariteSwitchConfig("relay_1", "relays.relay1.info.onoff", is_relay=True),
    AquariteSwitchConfig("relay_2", "relays.relay2.info.onoff", is_relay=True),
    AquariteSwitchConfig("relay_3", "relays.relay3.info.onoff", is_relay=True),
    AquariteSwitchConfig("relay_4", "relays.relay4.info.onoff", is_relay=True),
    AquariteSwitchConfig("filtration", "filtration.status"),
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aquarite switch platform."""
    dataservice = entry.runtime_data
    pool_id, pool_name = dataservice.pool_id, entry.title

    entities = [
        AquariteSwitchEntity(dataservice, pool_id, pool_name, config)
        for config in SWITCH_DEFINITIONS
    ]

    # HEAT mode "Climat" toggle
    if dataservice.get_value("filtration.hasHeat"):
        entities.append(
            AquariteSwitchEntity(
                dataservice, pool_id, pool_name,
                AquariteSwitchConfig(
                    "heating_climate", "filtration.heating.clima",
                ),
            )
        )

    # SMART mode "Antigel" (freeze protection) toggle.
    if dataservice.get_value("filtration.hasSmart"):
        entities.append(
            AquariteSwitchEntity(
                dataservice, pool_id, pool_name,
                AquariteSwitchConfig(
                    "smart_mode_freeze", "filtration.smart.freeze",
                ),
            )
        )

    async_add_entities(entities)


class AquariteSwitchEntity(AquariteEntity, SwitchEntity):
    """Representation of an Aquarite switch."""

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        config: AquariteSwitchConfig,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, pool_id, pool_name)
        self._value_path = config.value_path
        self._is_relay = config.is_relay
        self._attr_translation_key = config.translation_key
        self._attr_unique_id = self.build_unique_id(config.translation_key)

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        onoff = bool(int(self.coordinator.get_value(self._value_path) or 0))
        if self._is_relay:
            path_parts = self._value_path.split(".")
            status_path = ".".join([*path_parts[:-1], "status"])
            status = bool(int(self.coordinator.get_value(status_path) or 0))
            return onoff or status
        return onoff

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.coordinator.api.set_value(self._pool_id, self._value_path, 1)
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.coordinator.api.set_value(self._pool_id, self._value_path, 0)
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
