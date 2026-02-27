"""Push coordinator for madVR Envy integration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from madvr_envy import MadvrEnvyClient
from madvr_envy import exceptions as envy_exceptions
from madvr_envy.adapter import EnvyStateAdapter
from madvr_envy.ha_bridge import HABridgeDispatcher, coordinator_payload

from .const import (
    DEFAULT_SYNC_TIMEOUT,
    DOMAIN,
)


class MadvrEnvyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Bridge madvr_envy push updates into Home Assistant entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MadvrEnvyClient,
        *,
        sync_timeout: float = DEFAULT_SYNC_TIMEOUT,
    ) -> None:
        super().__init__(hass, logger=client.logger, name=DOMAIN)
        self.client = client
        self._sync_timeout = sync_timeout

        self._adapter = EnvyStateAdapter()
        self._dispatcher = HABridgeDispatcher(event_emitter=self._emit_bus_event)

        self._adapter_callback_handle: Any | None = None
        self._client_callback_registered = False
        self._started = False

    async def async_start(self) -> None:
        """Start client and register callbacks once."""
        if self._started:
            return

        if self._adapter_callback_handle is None:
            self._adapter_callback_handle = self.client.register_adapter_callback(
                self._adapter,
                self._handle_adapter_update,
            )

        if not self._client_callback_registered:
            self.client.register_callback(self._handle_client_event)
            self._client_callback_registered = True

        await self.client.start()
        await self.client.wait_synced(timeout=self._sync_timeout)
        await self._prime_state()

        snapshot, _, _ = self._adapter.update(self.client.state)
        self.async_set_updated_data(coordinator_payload(snapshot))
        self._started = True

    async def async_shutdown(self) -> None:
        """Stop runtime and clean callbacks."""
        if self._adapter_callback_handle is not None:
            self.client.deregister_adapter_callback(self._adapter_callback_handle)
            self._adapter_callback_handle = None

        if self._client_callback_registered:
            self.client.deregister_callback(self._handle_client_event)
            self._client_callback_registered = False

        await self.client.stop()
        self._started = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Return latest known data for manual refresh calls."""
        if self.data is not None:
            return deepcopy(self.data)

        snapshot, _, _ = self._adapter.update(self.client.state)
        return coordinator_payload(snapshot)

    def _emit_bus_event(self, event_type: str, event_data: dict[str, object]) -> None:
        self.hass.bus.async_fire(event_type, event_data)

    def _handle_adapter_update(self, snapshot, deltas, events) -> None:  # noqa: ANN001
        update = self._dispatcher.handle_adapter_update(snapshot, deltas, events)
        self.async_set_updated_data(update.coordinator_data)

    def _handle_client_event(self, event: str, _message: object | None = None) -> None:
        if event == "disconnected":
            self.async_set_updated_data(self._with_available(False))
        elif event == "connected":
            self.async_set_updated_data(self._with_available(True))

    def _with_available(self, available: bool) -> dict[str, Any]:
        if self.data is not None:
            data = dict(self.data)
            data["available"] = available
            return data

        snapshot, _, _ = self._adapter.update(self.client.state)
        data = coordinator_payload(snapshot)
        data["available"] = available
        return data

    async def _prime_state(self) -> None:
        """Best-effort startup priming for richer initial entity state."""
        try:
            await self.client.get_mac_address()
            await self.client.get_temperatures()

            groups = await self.client.enum_profile_groups_collect()
            for group in groups:
                await self.client.enum_profiles_collect(group.group_id)
        except (
            TimeoutError,
            envy_exceptions.MadvrEnvyError,
            OSError,
        ) as err:
            self.logger.debug("Startup priming skipped due to command failure: %s", err)
