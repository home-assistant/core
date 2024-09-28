"""Switch platform for La Marzocco espresso machines."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from lmcloud.const import BoilerType
from lmcloud.exceptions import RequestNotSuccessful
from lmcloud.lm_machine import LaMarzoccoMachine
from lmcloud.models import LaMarzoccoMachineConfig

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LaMarzoccoConfigEntry
from .const import DOMAIN
from .coordinator import LaMarzoccoUpdateCoordinator
from .entity import LaMarzoccoBaseEntity, LaMarzoccoEntity, LaMarzoccoEntityDescription


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoSwitchEntityDescription(
    LaMarzoccoEntityDescription,
    SwitchEntityDescription,
):
    """Description of a La Marzocco Switch."""

    control_fn: Callable[[LaMarzoccoMachine, bool], Coroutine[Any, Any, bool]]
    is_on_fn: Callable[[LaMarzoccoMachineConfig], bool]


ENTITIES: tuple[LaMarzoccoSwitchEntityDescription, ...] = (
    LaMarzoccoSwitchEntityDescription(
        key="main",
        translation_key="main",
        name=None,
        control_fn=lambda machine, state: machine.set_power(state),
        is_on_fn=lambda config: config.turned_on,
    ),
    LaMarzoccoSwitchEntityDescription(
        key="steam_boiler_enable",
        translation_key="steam_boiler",
        control_fn=lambda machine, state: machine.set_steam(state),
        is_on_fn=lambda config: config.boilers[BoilerType.STEAM].enabled,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities and services."""

    coordinator = entry.runtime_data

    entities: list[SwitchEntity] = []
    entities.extend(
        LaMarzoccoSwitchEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    )

    entities.extend(
        LaMarzoccoAutoOnOffSwitchEntity(coordinator, wake_up_sleep_entry_id)
        for wake_up_sleep_entry_id in coordinator.device.config.wake_up_sleep_entries
    )

    async_add_entities(entities)


class LaMarzoccoSwitchEntity(LaMarzoccoEntity, SwitchEntity):
    """Switches representing espresso machine power, prebrew, and auto on/off."""

    entity_description: LaMarzoccoSwitchEntityDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        try:
            await self.entity_description.control_fn(self.coordinator.device, True)
        except RequestNotSuccessful as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_on_error",
                translation_placeholders={"key": self.entity_description.key},
            ) from exc
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        try:
            await self.entity_description.control_fn(self.coordinator.device, False)
        except RequestNotSuccessful as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_off_error",
                translation_placeholders={"name": self.entity_description.key},
            ) from exc
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.entity_description.is_on_fn(self.coordinator.device.config)


class LaMarzoccoAutoOnOffSwitchEntity(LaMarzoccoBaseEntity, SwitchEntity):
    """Switch representing espresso machine auto on/off."""

    coordinator: LaMarzoccoUpdateCoordinator
    _attr_translation_key = "auto_on_off"

    def __init__(
        self,
        coordinator: LaMarzoccoUpdateCoordinator,
        identifier: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, f"auto_on_off_{identifier}")
        self._identifier = identifier
        self._attr_translation_placeholders = {"id": identifier}
        self.entity_category = EntityCategory.CONFIG

    async def _async_enable(self, state: bool) -> None:
        """Enable or disable the auto on/off schedule."""
        wake_up_sleep_entry = self.coordinator.device.config.wake_up_sleep_entries[
            self._identifier
        ]
        wake_up_sleep_entry.enabled = state
        try:
            await self.coordinator.device.set_wake_up_sleep(wake_up_sleep_entry)
        except RequestNotSuccessful as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auto_on_off_error",
                translation_placeholders={"id": self._identifier, "state": str(state)},
            ) from exc
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        await self._async_enable(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        await self._async_enable(False)

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.coordinator.device.config.wake_up_sleep_entries[
            self._identifier
        ].enabled
