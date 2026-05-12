"""Switch platform for Kiosker."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from kiosker import (
    AuthenticationError,
    BadRequestError,
    ConnectionError,
    IPAuthenticationError,
    KioskerAPI,
    TLSVerificationError,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KioskerConfigEntry
from .const import REFRESH_DELAY
from .coordinator import KioskerData
from .entity import KioskerEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class KioskerSwitchEntityDescription(SwitchEntityDescription):
    """Kiosker switch description."""

    set_state_fn: Callable[[KioskerAPI, bool], None]
    is_on_fn: Callable[[KioskerData], bool | None]


SWITCHES: tuple[KioskerSwitchEntityDescription, ...] = (
    KioskerSwitchEntityDescription(
        key="disableScreensaver",
        translation_key="disable_screensaver",
        set_state_fn=lambda api, disabled: api.screensaver_set_disabled_state(disabled),
        is_on_fn=lambda x: x.screensaver.disabled if x.screensaver else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KioskerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kiosker switches based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        KioskerSwitch(coordinator, description) for description in SWITCHES
    )


class KioskerSwitch(KioskerEntity, SwitchEntity):
    """Representation of a Kiosker switch."""

    entity_description: KioskerSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    async def _handle_method_call(self, state: bool) -> None:
        """Handle method call with error handling."""
        try:
            await self.hass.async_add_executor_job(
                self.entity_description.set_state_fn, self.coordinator.api, state
            )
        except AuthenticationError as exc:
            raise HomeAssistantError("Authentication failed") from exc
        except IPAuthenticationError as exc:
            raise HomeAssistantError("IP Authentication failed") from exc
        except ConnectionError as exc:
            raise HomeAssistantError(f"Connection failed: {exc}") from exc
        except TLSVerificationError as exc:
            raise HomeAssistantError(f"TLS verification failed: {exc}") from exc
        except BadRequestError as exc:
            raise ServiceValidationError(f"Bad request: {exc}") from exc

        await asyncio.sleep(REFRESH_DELAY)
        await self.coordinator.async_refresh()

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn the switch on."""
        await self._handle_method_call(True)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn the switch off."""
        await self._handle_method_call(False)
