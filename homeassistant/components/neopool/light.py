"""Light platform for the NeoPool integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from neopool_modbus import NeoPoolInvalidStateError
from neopool_modbus.registers import RelayKind, TimerRelayMode, is_valid_relay_gpio

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_USE_LIGHT, DOMAIN
from .coordinator import NeoPoolConfigEntry, NeoPoolCoordinator
from .entity import NeoPoolEntity

PARALLEL_UPDATES = 1

_LIGHT_TIMER_ENABLE_KEY = "relay_light_enable"


@dataclass(frozen=True, kw_only=True)
class NeoPoolLightEntityDescription(LightEntityDescription):
    """Describes a NeoPool light entity."""

    supported_fn: Callable[[dict[str, Any]], bool] | None = None


LIGHT_DESCRIPTIONS: dict[str, NeoPoolLightEntityDescription] = {
    "light": NeoPoolLightEntityDescription(
        key="light",
        translation_key="light",
        supported_fn=lambda data: (
            "MBF_PAR_LIGHTING_GPIO" in data
            and is_valid_relay_gpio(data["MBF_PAR_LIGHTING_GPIO"] or 0)
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NeoPool lights from a config entry."""
    coordinator = entry.runtime_data

    if not entry.options.get(CONF_USE_LIGHT):
        return

    async_add_entities(
        NeoPoolLight(coordinator, key, desc)
        for key, desc in LIGHT_DESCRIPTIONS.items()
        if desc.supported_fn is None or desc.supported_fn(coordinator.data)
    )


class NeoPoolLight(NeoPoolEntity, LightEntity):
    """Representation of a NeoPool light entity."""

    entity_description: NeoPoolLightEntityDescription
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(
        self,
        coordinator: NeoPoolCoordinator,
        key: str,
        description: NeoPoolLightEntityDescription,
    ) -> None:
        """Initialize the NeoPool light entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.unique_id}_{key.lower()}"
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light ON."""
        await self._async_set_state(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light OFF."""
        await self._async_set_state(False)

    async def _async_set_state(self, state: bool) -> None:
        """Drive the light relay via its timer block."""
        if self.coordinator.data.get(_LIGHT_TIMER_ENABLE_KEY) not in (
            TimerRelayMode.ALWAYS_ON,
            TimerRelayMode.ALWAYS_OFF,
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="relay_in_auto_mode",
            )

        try:
            overrides = await self.coordinator.client.async_set_relay_state(
                RelayKind.LIGHT, state
            )
        except NeoPoolInvalidStateError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="relay_in_auto_mode",
            ) from err

        # Optimistic update + schedule follow-up.
        self.coordinator.async_set_updated_data({**self.coordinator.data, **overrides})
        self.coordinator.request_refresh_with_followup()

    @property
    @override
    def is_on(self) -> bool:
        """Return True if the light is ON."""
        return bool(self.coordinator.data.get("Pool Light"))
