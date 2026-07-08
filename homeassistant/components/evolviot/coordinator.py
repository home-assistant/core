"""Data coordinator for EvolvIOT."""

import asyncio
import logging
from typing import Any, override

from pyevolviot import EvolvIOTApi, EvolvIOTApiError, EvolvIOTAuthError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, STORAGE_KEY_PREFIX, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class EvolvIOTDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch EvolvIOT entities and states on a shared schedule."""

    def __init__(self, hass: HomeAssistant, api: EvolvIOTApi, entry_id: str) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api = api
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}.{entry_id}",
        )
        self._cached_devices_payload: dict[str, Any] | None = None

    async def async_load_cache(self) -> None:
        """Load cached device metadata for offline startup."""
        stored = await self._store.async_load()
        if not isinstance(stored, dict):
            return

        devices_payload = stored.get("devices_payload")
        if isinstance(devices_payload, dict):
            self._cached_devices_payload = devices_payload

    @property
    def entities(self) -> dict[str, dict[str, Any]]:
        """Return entities keyed by backend entity id."""
        data = self.data or {}
        entities = data.get("entities", {})
        return entities if isinstance(entities, dict) else {}

    @property
    def states(self) -> dict[str, dict[str, Any]]:
        """Return states keyed by backend entity id."""
        data = self.data or {}
        states = data.get("states", {})
        return states if isinstance(states, dict) else {}

    def entities_for_domain(self, domain: str) -> list[dict[str, Any]]:
        """Return entities for one Home Assistant platform domain."""
        return [
            entity
            for entity in self.entities.values()
            if entity.get("domain") == domain
        ]

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh data from EvolvIOT."""
        states_payload: dict[str, Any] = {}
        cloud_error: EvolvIOTApiError | None = None

        try:
            devices_payload = await self.api.async_get_devices()
        except EvolvIOTAuthError as err:
            raise UpdateFailed(str(err)) from err
        except EvolvIOTApiError as err:
            cloud_error = err
            devices_payload = self._cached_devices_payload or {}
        else:
            await self._async_save_cached_devices_payload(devices_payload)
            try:
                states_payload = await self.api.async_get_states()
            except EvolvIOTApiError as err:
                cloud_error = err

        entities = {
            str(entity.get("entity_id")): entity
            for entity in devices_payload.get("entities", [])
            if entity.get("entity_id")
        }

        if not entities and cloud_error is not None:
            raise UpdateFailed(str(cloud_error)) from cloud_error

        states = {
            str(state.get("entity_id")): state
            for state in states_payload.get("states", [])
            if state.get("entity_id")
        }
        local_statuses = await self._async_local_statuses(
            str(devices_payload.get("user_id") or ""),
            entities,
        )

        for entity_id, local_status in local_statuses.items():
            has_cloud_state = entity_id in states
            state = dict(states.get(entity_id) or {"entity_id": entity_id})
            state["cloud_available"] = (
                bool(state.get("available", True)) if has_cloud_state else False
            )
            is_available = bool(local_status.get("available"))
            state["local_available"] = is_available
            if is_available:
                state["available"] = True
            elif "available" not in state:
                state["available"] = False
            if "value" in local_status:
                self._apply_local_state(
                    state,
                    local_status["value"],
                )
            states[entity_id] = state

        return {
            "user_id": devices_payload.get("user_id"),
            "entities": entities,
            "states": states,
        }

    async def _async_save_cached_devices_payload(
        self,
        devices_payload: dict[str, Any],
    ) -> None:
        """Persist device metadata needed for local-only operation."""
        if not devices_payload.get("entities"):
            return

        self._cached_devices_payload = devices_payload
        await self._store.async_save({"devices_payload": devices_payload})

    async def _async_local_statuses(
        self,
        uid: str,
        entities: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Fetch local status once per physical local-capable device."""
        if not uid:
            return {}

        device_checks: dict[tuple[str, str], asyncio.Task[dict[str, Any] | None]] = {}
        entity_devices: dict[str, tuple[str, str]] = {}

        for entity_id, entity in entities.items():
            device = entity.get("device") or {}
            local_control = (
                device.get("local_control") or entity.get("local_control") or {}
            )
            if local_control.get("enabled") is False:
                continue

            device_id = str(device.get("id") or "").strip()
            device_secret = str(
                local_control.get("device_secret")
                or local_control.get("deviceSecret")
                or ""
            ).strip()
            if not device_id or not device_secret:
                continue

            key = (device_id, device_secret)
            entity_devices[entity_id] = key
            if key not in device_checks:
                device_checks[key] = self.hass.async_create_task(
                    self._async_local_device_status(
                        uid,
                        device_id,
                        device_secret,
                    )
                )

        if not device_checks:
            return {}

        results = await asyncio.gather(*device_checks.values())
        status_by_device = dict(zip(device_checks.keys(), results, strict=True))
        local_statuses: dict[str, dict[str, Any]] = {}

        for entity_id, device_key in entity_devices.items():
            local_data = status_by_device.get(device_key)
            local_status: dict[str, Any] = {"available": local_data is not None}
            if local_data is not None:
                local_value = self._local_value_for_entity(
                    entities[entity_id], local_data
                )
                if local_value is not None:
                    local_status["value"] = local_value
            local_statuses[entity_id] = local_status

        return local_statuses

    async def _async_local_device_status(
        self,
        uid: str,
        device_id: str,
        device_secret: str,
    ) -> dict[str, Any] | None:
        """Return local device status data when reachable."""
        try:
            return await self.api.async_local_status(
                uid=uid,
                device_id=device_id,
                device_secret=device_secret,
            )
        except EvolvIOTApiError:
            return None

    def _local_value_for_entity(
        self,
        entity: dict[str, Any],
        local_data: dict[str, Any],
    ) -> Any:
        """Return this entity's value from a local device status payload."""
        device = entity.get("device") or {}
        local_control = device.get("local_control") or entity.get("local_control") or {}
        control = entity.get("control") or {}
        candidates = [
            local_control.get("status_key"),
            local_control.get("statusKey"),
            local_control.get("switch_name"),
            local_control.get("switchName"),
            control.get("key"),
            control.get("name"),
            control.get("appliance_name"),
        ]

        for candidate in candidates:
            key = str(candidate or "").strip()
            if key and key in local_data:
                return local_data[key]

        normalized_local_data = {
            self._normalize_local_status_key(key): value
            for key, value in local_data.items()
        }
        for candidate in candidates:
            normalized_key = self._normalize_local_status_key(candidate)
            if normalized_key and normalized_key in normalized_local_data:
                return normalized_local_data[normalized_key]
        return None

    @staticmethod
    def _normalize_local_status_key(value: Any) -> str:
        """Normalize local status keys for tolerant matching."""
        return "".join(
            character for character in str(value or "").lower() if character.isalnum()
        )

    def _apply_local_state(
        self,
        state: dict[str, Any],
        value: Any,
    ) -> None:
        """Apply a local status value to a Home Assistant state payload."""
        state["raw_value"] = value

        try:
            is_on = float(value) > 0
        except TypeError, ValueError:
            is_on = str(value).lower() in {"on", "true", "1"}

        state["state"] = "on" if is_on else "off"
