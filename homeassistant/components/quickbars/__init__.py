"""The QuickBars for Home Assistant Integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import logging
import secrets

from quickbars_bridge.hass_helpers import build_notify_payload
from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser

from homeassistant import config_entries
from homeassistant.components import persistent_notification, zeroconf as ha_zc
from homeassistant.components.zeroconf import HaAsyncZeroconf
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .constants import ATTR_DEVICE_ID, DOMAIN, SERVICE_TYPE
from .coordinator import QuickBarsCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

# Typed config entry for this integration
type QuickBarsConfigEntry = config_entries.ConfigEntry["QuickBarsRuntime"]


@dataclass(slots=True)
class QuickBarsRuntime:
    """Runtime data for a QuickBars config entry."""

    device_id: str
    presence: _Presence
    coordinator: QuickBarsCoordinator
    unsub_action: Callable[[], None] | None


class _Presence:
    """Zeroconf: track the app instance and keep host/port fresh."""

    def __init__(self, hass: HomeAssistant, entry: config_entries.ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._browser: AsyncServiceBrowser | None = None
        self._aiozc: HaAsyncZeroconf | None = None

    async def start(self) -> None:
        self._aiozc = await ha_zc.async_get_async_instance(self.hass)
        if self._aiozc:
            self._browser = AsyncServiceBrowser(
                self._aiozc.zeroconf, SERVICE_TYPE, handlers=[self._on_change]
            )

    async def stop(self) -> None:
        if self._browser:
            await self._browser.async_cancel()
            self._browser = None

    def _on_change(self, *args, **kwargs) -> None:
        if kwargs:
            service_type = kwargs.get("service_type")
            name = kwargs.get("name")
            state_change = kwargs.get("state_change")
        else:
            _, service_type, name, state_change = args

        if (
            isinstance(service_type, str)
            and isinstance(name, str)
            and isinstance(state_change, ServiceStateChange)
        ):
            self.hass.async_create_task(
                self._handle_change(service_type, name, state_change)
            )

    async def _handle_change(
        self, service_type: str, name: str, state_change: ServiceStateChange
    ) -> None:
        if service_type != SERVICE_TYPE:
            return

        wanted_id = (
            (self.entry.data.get(CONF_ID) or self.entry.unique_id or "").strip().lower()
        )

        if state_change is ServiceStateChange.Removed:
            return

        if self._aiozc is None:
            return

        info = await self._aiozc.async_get_service_info(service_type, name, 3000)
        if not info:
            return

        props: dict[str, str] = {}
        for k, v in (info.properties or {}).items():
            key = k.decode() if isinstance(k, (bytes, bytearray)) else str(k)
            val = v.decode() if isinstance(v, (bytes, bytearray)) else str(v)
            props[key] = val

        found_id = (props.get("id") or "").strip().lower()
        if not found_id or found_id != wanted_id:
            return

        host = (info.parsed_addresses() or [self.entry.data.get(CONF_HOST) or ""])[0]
        port = info.port or self.entry.data.get(CONF_PORT)
        if (
            host
            and port
            and (
                host != self.entry.data.get(CONF_HOST)
                or port != self.entry.data.get(CONF_PORT)
            )
        ):
            new_data = {**self.entry.data, CONF_HOST: host, CONF_PORT: port}
            _LOGGER.debug("Presence: updating host/port -> %s:%s", host, port)
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)

            rt = getattr(self.entry, "runtime_data", None)
            if rt is not None:
                self.hass.async_create_task(rt.coordinator.async_request_refresh())


def _entry_for_device(
    hass: HomeAssistant, device_id: str | None
) -> config_entries.ConfigEntry | None:
    """Resolve config entry from a HA device_id; fallback if only one entry exists."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if device_id:
        dev = dr.async_get(hass).async_get(device_id)
        if dev:
            ident = next((v for (d, v) in dev.identifiers if d == DOMAIN), None)
            if ident:
                for ent in entries:
                    if ident in (
                        ent.data.get(CONF_ID),
                        ent.unique_id,
                        ent.entry_id,
                    ):
                        return ent
    if len(entries) == 1:
        return entries[0]
    return None  # ambiguous or none configured


async def _svc_notify(hass: HomeAssistant, call: ServiceCall) -> None:
    """Service handler for notify."""
    target_device_id = call.data.get(ATTR_DEVICE_ID)
    entry2 = _entry_for_device(hass, target_device_id) if target_device_id else None

    payload = await build_notify_payload(hass, call.data)
    if entry2:
        payload[CONF_ID] = (
            entry2.data.get(CONF_ID) or entry2.unique_id or entry2.entry_id
        )

    cid = call.data.get("cid") or secrets.token_urlsafe(8)
    payload["cid"] = cid

    hass.bus.async_fire("quickbars.notify", payload)

    if entry2:
        dev_id = entry2.runtime_data.device_id
        hass.bus.async_fire(
            f"{DOMAIN}.notification_sent",
            {
                **({"device_id": dev_id} if dev_id else {}),
                "entry_id": entry2.entry_id,
                "cid": cid,
                "title": payload.get("title"),
            },
        )


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Register global service actions so they exist even without entries."""
    hass.services.async_register(DOMAIN, "notify", partial(_svc_notify, hass))
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Per-entry setup: presence tracking, coordinator, device registration, and action -> HA event bridge."""
    # Create a Device for device_id targeting
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        manufacturer="QuickBars",
        name=entry.title or "QuickBars TV",
    )

    # Presence (Zeroconf) and connectivity
    presence = _Presence(hass, entry)
    await presence.start()

    coordinator = QuickBarsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Bridge TV button clicks -> HA event (per-entry)
    def _on_action(evt):
        data = evt.data or {}
        exp_id = entry.data.get(CONF_ID) or entry.unique_id or entry.entry_id
        incoming_id = data.get(CONF_ID)
        if incoming_id and incoming_id != exp_id:
            return
        hass.bus.async_fire(
            f"{DOMAIN}.notification_action",
            {
                "device_id": entry.runtime_data.device_id,
                "entry_id": entry.entry_id,
                "cid": data.get("cid"),
                "action_id": data.get("action_id"),
                "label": data.get("label"),
            },
        )

    unsub_action = hass.bus.async_listen("quickbars.action", _on_action)

    entry.runtime_data = QuickBarsRuntime(
        device_id=device.id,
        presence=presence,
        coordinator=coordinator,
        unsub_action=unsub_action,
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a QuickBars config entry and clean up resources."""
    rt = getattr(entry, "runtime_data", None)
    if rt:
        if rt.presence:
            await rt.presence.stop()
        if rt.unsub_action:
            rt.unsub_action()
    return True


async def async_remove_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> None:
    """Called after an entry is removed (after unload)."""
    persistent_notification.async_create(
        hass,
        (
            "The QuickBars integration for a specific TV was removed from Home Assistant.\n\n"
            "If the QuickBars TV app is still paired, open the app → Settings "
            "→ Manage HA Integration → Reset Pairing to clean up pairing on the TV."
        ),
        title="QuickBars integration removed",
    )
