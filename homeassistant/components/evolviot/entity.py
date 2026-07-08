"""Base entities for EvolvIOT."""

import asyncio
from contextlib import suppress
from typing import Any, override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EvolvIOTDataUpdateCoordinator


class EvolvIOTEntity(CoordinatorEntity[EvolvIOTDataUpdateCoordinator]):
    """Base EvolvIOT entity."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: EvolvIOTDataUpdateCoordinator,
        entity: dict[str, Any],
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._backend_entity_id = str(entity["entity_id"])
        self._fallback_entity = entity
        self._attr_unique_id = str(entity.get("unique_id") or self._backend_entity_id)
        self._attr_name = str(entity.get("name") or self._backend_entity_id)

        device = entity.get("device") or {}
        device_id = str(device.get("id") or self._attr_unique_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=str(device.get("name") or "EvolvIOT Device"),
            manufacturer=str(device.get("manufacturer") or "EvolvIOT"),
            model=str(device.get("model") or "") or None,
        )

    @property
    def backend_entity(self) -> dict[str, Any]:
        """Return latest backend entity metadata."""
        return self.coordinator.entities.get(
            self._backend_entity_id, self._fallback_entity
        )

    @property
    def backend_state(self) -> dict[str, Any]:
        """Return latest backend state."""
        return self.coordinator.states.get(self._backend_entity_id, {})

    @property
    @override
    def available(self) -> bool:
        """Return availability from cloud or local device reachability."""
        state = self.backend_state
        if not state:
            return False
        return bool(state.get("available", True) or state.get("local_available"))

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose useful EvolvIOT metadata."""
        entity = self.backend_entity
        state = self.backend_state
        local_available = bool(state.get("local_available"))
        cloud_available = bool(state) and bool(
            state.get("cloud_available", state.get("available", True))
        )
        return {
            "evolviot_entity_id": self._backend_entity_id,
            "connection_mode": self._connection_mode(
                cloud_available,
                local_available,
            ),
            "cloud_available": cloud_available,
            "local_available": local_available,
            "raw_value": state.get("raw_value"),
            "control": entity.get("control") or {},
        }

    @staticmethod
    def _connection_mode(cloud_available: bool, local_available: bool) -> str:
        """Return the active connection mode label."""
        if local_available:
            return "local"
        if cloud_available:
            return "cloud"
        return "offline"

    async def _async_send_command(self, payload: dict[str, Any]) -> None:
        """Send a command through cloud and local paths when available."""
        local_command = self._local_command(payload)
        if local_command is None:
            await self.coordinator.api.async_command(self._backend_entity_id, payload)
            self._apply_optimistic_state(payload)
            self._schedule_refresh()
            return

        if self.backend_state.get("local_available"):
            await self._async_send_prefer_local(payload, local_command)
        else:
            await self._async_send_first_success(payload, local_command)
        self._apply_optimistic_state(payload)
        self._schedule_refresh()

    async def _async_send_first_success(
        self,
        cloud_payload: dict[str, Any],
        local_command: dict[str, Any],
    ) -> None:
        """Run cloud and local commands in parallel and return on first success."""
        tasks = {
            self.hass.async_create_task(
                self.coordinator.api.async_command(
                    self._backend_entity_id,
                    cloud_payload,
                )
            ),
            self.hass.async_create_task(
                self.coordinator.api.async_local_command(**local_command)
            ),
        }
        errors: list[BaseException] = []

        while tasks:
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                try:
                    await task
                except Exception as err:  # noqa: BLE001
                    errors.append(err)
                    continue

                for pending_task in pending:
                    pending_task.cancel()
                for pending_task in pending:
                    with suppress(asyncio.CancelledError, Exception):
                        await pending_task
                return

            tasks = pending

        if errors:
            raise errors[0]

    async def _async_send_prefer_local(
        self,
        cloud_payload: dict[str, Any],
        local_command: dict[str, Any],
    ) -> None:
        """Run cloud and local commands together, but require local when reachable."""
        cloud_task = self.hass.async_create_task(
            self.coordinator.api.async_command(
                self._backend_entity_id,
                cloud_payload,
            )
        )
        local_task = self.hass.async_create_task(
            self.coordinator.api.async_local_command(**local_command)
        )

        cloud_error: BaseException | None = None
        try:
            await local_task
        except Exception as local_error:
            try:
                await cloud_task
            except Exception as err:  # noqa: BLE001
                cloud_error = err
            if cloud_error is not None:
                raise local_error from cloud_error
        else:
            if not cloud_task.done():
                cloud_task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await cloud_task

    def _local_command(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Build local encrypted command details when entity metadata supports it."""
        value = self._local_command_value(payload)
        if value is None:
            return None

        entity = self.backend_entity
        device = entity.get("device") or {}
        local_control = device.get("local_control") or entity.get("local_control") or {}
        if local_control.get("enabled") is False:
            return None

        control = entity.get("control") or {}
        uid = str((self.coordinator.data or {}).get("user_id") or "").strip()
        device_id = str(device.get("id") or "").strip()
        device_secret = str(
            local_control.get("device_secret")
            or local_control.get("deviceSecret")
            or ""
        ).strip()
        switch_name = str(
            local_control.get("switch_name")
            or local_control.get("switchName")
            or local_control.get("status_key")
            or local_control.get("statusKey")
            or control.get("key")
            or ""
        ).strip()
        endpoint = str(local_control.get("endpoint") or "").strip()
        if not endpoint or endpoint == "control":
            endpoint = switch_name

        if not all((uid, device_id, device_secret, switch_name, endpoint)):
            return None

        return {
            "uid": uid,
            "device_id": device_id,
            "endpoint": endpoint,
            "device_secret": device_secret,
            "switch_name": switch_name,
            "value": value,
        }

    def _local_command_value(self, payload: dict[str, Any]) -> Any | None:
        """Map Home Assistant command payload to local ESP command value."""
        command = payload.get("command")
        if command == "turn_on":
            return 1
        if command == "turn_off":
            return 0
        return None

    def _apply_optimistic_state(self, payload: dict[str, Any]) -> None:
        """Reflect a successful command immediately while backend state settles."""
        data = self.coordinator.data
        if not isinstance(data, dict):
            return
        states = data.get("states")
        if not isinstance(states, dict):
            return

        state = dict(states.get(self._backend_entity_id) or {})
        attributes = dict(state.get("attributes") or {})
        command = payload.get("command")

        if command == "turn_on":
            state["state"] = "on"
        elif command == "turn_off":
            state["state"] = "off"

        state["available"] = True
        if attributes:
            state["attributes"] = attributes
        states[self._backend_entity_id] = state
        self.async_write_ha_state()

    def _schedule_refresh(self) -> None:
        """Refresh after a short delay to avoid rendering stale command state."""
        self.hass.async_create_task(self._async_delayed_refresh())

    async def _async_delayed_refresh(self) -> None:
        """Request a delayed coordinator refresh."""
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()
