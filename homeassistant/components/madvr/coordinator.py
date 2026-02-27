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
    ASPECT_DEC,
    ASPECT_INT,
    ASPECT_NAME,
    ASPECT_RES,
    DEFAULT_SYNC_TIMEOUT,
    DOMAIN,
    INCOMING_ASPECT_RATIO,
    INCOMING_BIT_DEPTH,
    INCOMING_BLACK_LEVELS,
    INCOMING_COLORIMETRY,
    INCOMING_COLOR_SPACE,
    INCOMING_FRAME_RATE,
    INCOMING_RES,
    INCOMING_SIGNAL_TYPE,
    MASKING_DEC,
    MASKING_INT,
    MASKING_RES,
    OUTGOING_BIT_DEPTH,
    OUTGOING_BLACK_LEVELS,
    OUTGOING_COLORIMETRY,
    OUTGOING_COLOR_SPACE,
    OUTGOING_FRAME_RATE,
    OUTGOING_RES,
    OUTGOING_SIGNAL_TYPE,
    TEMP_CPU,
    TEMP_GPU,
    TEMP_HDMI,
    TEMP_MAINBOARD,
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
        self.mac = f"{self.client.host}_{self.client.port}"

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
        self.async_set_updated_data(self._legacy_payload(coordinator_payload(snapshot)))
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
        return self._legacy_payload(coordinator_payload(snapshot))

    def _emit_bus_event(self, event_type: str, event_data: dict[str, object]) -> None:
        self.hass.bus.async_fire(event_type, event_data)

    def _handle_adapter_update(self, snapshot, deltas, events) -> None:  # noqa: ANN001
        update = self._dispatcher.handle_adapter_update(snapshot, deltas, events)
        self.async_set_updated_data(self._legacy_payload(update.coordinator_data))

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
        data = self._legacy_payload(coordinator_payload(snapshot))
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

    def _legacy_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Map adapter payload to legacy madVR keys for entity compatibility."""
        data = dict(payload)

        mac_address = data.get("mac_address")
        if isinstance(mac_address, str) and mac_address:
            self.mac = mac_address.lower().replace(":", "")

        temperatures = data.get("temperatures")
        if isinstance(temperatures, (list, tuple)):
            if len(temperatures) > 0:
                data[TEMP_GPU] = temperatures[0]
            if len(temperatures) > 1:
                data[TEMP_HDMI] = temperatures[1]
            if len(temperatures) > 2:
                data[TEMP_CPU] = temperatures[2]
            if len(temperatures) > 3:
                data[TEMP_MAINBOARD] = temperatures[3]

        incoming = data.get("incoming_signal")
        if isinstance(incoming, dict):
            data[INCOMING_RES] = incoming.get("resolution")
            data[INCOMING_SIGNAL_TYPE] = incoming.get("signal_type")
            data[INCOMING_FRAME_RATE] = incoming.get("frame_rate")
            data[INCOMING_COLOR_SPACE] = incoming.get("color_space")
            data[INCOMING_BIT_DEPTH] = incoming.get("bit_depth")
            data[INCOMING_COLORIMETRY] = incoming.get("colorimetry")
            data[INCOMING_BLACK_LEVELS] = incoming.get("black_levels")
            data[INCOMING_ASPECT_RATIO] = incoming.get("aspect_ratio")
            hdr_mode = incoming.get("hdr_mode")
            data["hdr_flag"] = isinstance(hdr_mode, str) and hdr_mode.upper() != "SDR"

        outgoing = data.get("outgoing_signal")
        if isinstance(outgoing, dict):
            data[OUTGOING_RES] = outgoing.get("resolution")
            data[OUTGOING_SIGNAL_TYPE] = outgoing.get("signal_type")
            data[OUTGOING_FRAME_RATE] = outgoing.get("frame_rate")
            data[OUTGOING_COLOR_SPACE] = outgoing.get("color_space")
            data[OUTGOING_BIT_DEPTH] = outgoing.get("bit_depth")
            data[OUTGOING_COLORIMETRY] = outgoing.get("colorimetry")
            data[OUTGOING_BLACK_LEVELS] = outgoing.get("black_levels")
            hdr_mode = outgoing.get("hdr_mode")
            data["outgoing_hdr_flag"] = (
                isinstance(hdr_mode, str) and hdr_mode.upper() != "SDR"
            )

        aspect_ratio = data.get("aspect_ratio")
        if isinstance(aspect_ratio, dict):
            data[ASPECT_RES] = aspect_ratio.get("resolution")
            data[ASPECT_DEC] = aspect_ratio.get("decimal_ratio")
            data[ASPECT_INT] = aspect_ratio.get("integer_ratio")
            data[ASPECT_NAME] = aspect_ratio.get("name")

        masking_ratio = data.get("masking_ratio")
        if isinstance(masking_ratio, dict):
            data[MASKING_RES] = masking_ratio.get("resolution")
            data[MASKING_DEC] = masking_ratio.get("decimal_ratio")
            data[MASKING_INT] = masking_ratio.get("integer_ratio")

        data["is_on"] = data.get("power_state") != "off"
        data["is_signal"] = bool(data.get("signal_present"))
        return data
