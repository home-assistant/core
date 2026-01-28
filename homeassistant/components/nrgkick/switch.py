"""Switch platform for NRGkick."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import NRGkickApiClientInvalidResponseError, async_api_call
from .const import DOMAIN
from .coordinator import NRGkickConfigEntry, NRGkickData, NRGkickDataUpdateCoordinator
from .entity import NRGkickEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NRGkickSwitchEntityDescription(SwitchEntityDescription):
    """Class describing NRGkick switch entities."""

    is_on_fn: Callable[[NRGkickData], bool]
    set_pause_fn: Callable[
        [NRGkickDataUpdateCoordinator, bool], Awaitable[dict[str, Any]]
    ]


def _is_charging_enabled(data: NRGkickData) -> bool:
    """Return True if charging is enabled (not paused)."""
    charge_pause = data.control.get("charge_pause")
    return charge_pause == 0


async def _async_set_charge_pause(
    coordinator: NRGkickDataUpdateCoordinator, pause: bool
) -> dict[str, Any]:
    """Set the charge pause state."""
    response = await async_api_call(coordinator.api.set_charge_pause(pause))

    if (reason := response.get("Response")) and isinstance(reason, str):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_rejected",
            translation_placeholders={"reason": reason},
        )

    if "charge_pause" not in response:
        raise NRGkickApiClientInvalidResponseError

    try:
        charge_pause = int(response["charge_pause"])
    except (TypeError, ValueError) as err:
        raise NRGkickApiClientInvalidResponseError from err

    expected = 1 if pause else 0
    if charge_pause != expected:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_rejected",
            translation_placeholders={
                "reason": f"Unexpected charge_pause value: {charge_pause}",
            },
        )

    return response


SWITCHES: tuple[NRGkickSwitchEntityDescription, ...] = (
    NRGkickSwitchEntityDescription(
        key="charging_enabled",
        translation_key="charging_enabled",
        is_on_fn=_is_charging_enabled,
        # API expects pause=True to stop charging
        set_pause_fn=_async_set_charge_pause,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick switches based on a config entry."""
    coordinator: NRGkickDataUpdateCoordinator = entry.runtime_data

    async_add_entities(
        NRGkickSwitch(coordinator, description) for description in SWITCHES
    )


class NRGkickSwitch(NRGkickEntity, SwitchEntity):
    """Representation of a NRGkick switch."""

    entity_description: NRGkickSwitchEntityDescription

    def __init__(
        self,
        coordinator: NRGkickDataUpdateCoordinator,
        entity_description: NRGkickSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        data = self.coordinator.data
        assert data is not None
        return self.entity_description.is_on_fn(data)

    def _optimistic_set_charge_pause(self, pause: bool) -> None:
        """Optimistically update the cached control data.

        This makes state changes visible immediately after a successful command,
        while a background coordinator refresh verifies the actual device state.
        """
        self.coordinator.async_update_control_cache({"charge_pause": 1 if pause else 0})

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on (enable charging)."""
        await self.entity_description.set_pause_fn(self.coordinator, False)
        self._optimistic_set_charge_pause(False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off (pause charging)."""
        await self.entity_description.set_pause_fn(self.coordinator, True)
        self._optimistic_set_charge_pause(True)
