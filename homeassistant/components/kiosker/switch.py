"""Switch platform for Kiosker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from kiosker import (
    AuthenticationError,
    BadRequestError,
    ConnectionError,
    IPAuthenticationError,
    TLSVerificationError,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KioskerConfigEntry
from .coordinator import KioskerData, KioskerDataUpdateCoordinator
from .entity import KioskerEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class KioskerSwitchEntityDescription(SwitchEntityDescription):
    """Kiosker switch description."""

    method: str
    is_on_fn: Callable[[KioskerData], bool | None]


SWITCHES: tuple[KioskerSwitchEntityDescription, ...] = (
    KioskerSwitchEntityDescription(
        key="disableScreensaver",
        translation_key="disable_screensaver",
        method="async_set_screensaver_disabled",
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

    def __init__(
        self,
        coordinator: KioskerDataUpdateCoordinator,
        description: KioskerSwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, description)
        self._method = getattr(self, description.method)
        self._control_result: bool | None = None

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        # Use optimistic state if available (during API calls)
        if self._control_result is not None:
            return self._control_result

        return self.entity_description.is_on_fn(self.coordinator.data)

    async def _handle_method_call(self, state: bool, action: str) -> None:
        """Handle method call with error handling and state management."""
        try:
            await self._method(state)
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
        except Exception as exc:
            _LOGGER.exception("Unexpected error %s switch", action)
            raise HomeAssistantError(f"Unexpected error: {exc}") from exc

        # Set optimistic state for immediate UI feedback
        self._control_result = state
        self.async_write_ha_state()

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn the switch on."""
        await self._handle_method_call(True, "turning on")

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn the switch off."""
        await self._handle_method_call(False, "turning off")

    async def async_set_screensaver_disabled(self, disabled: bool) -> None:
        """Set screensaver disabled state."""
        await self.hass.async_add_executor_job(
            self.coordinator.api.screensaver_set_disabled_state, disabled
        )
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        # Clear optimistic state when real data arrives
        self._control_result = None
        super()._handle_coordinator_update()
