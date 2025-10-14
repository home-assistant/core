"""The QuickBars for Home Assistant Integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import logging
import secrets
from typing import Any

from quickbars_bridge.hass_helpers import build_notify_payload
import voluptuous as vol
from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser

from homeassistant import config_entries
from homeassistant.components import persistent_notification, zeroconf as ha_zc
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .constants import DOMAIN, EVENT_NAME, POS_CHOICES, SERVICE_TYPE
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


# ----- Service Schemas -----
QUICKBAR_SCHEMA = vol.Schema(
    {
        vol.Required("alias"): cv.string,
        vol.Optional("device_id"): cv.string,
    }
)

CAMERA_SCHEMA = vol.Schema(
    {
        # Exactly one of these:
        vol.Exclusive("camera_alias", "cam_id"): cv.string,
        vol.Exclusive("camera_entity", "cam_id"): cv.entity_id,
        vol.Optional("rtsp_url"): cv.string,
        # Optional rendering options
        vol.Optional("position"): vol.In(POS_CHOICES),
        # Either preset size OR custom size in px
        vol.Exclusive("size", "cam_size"): vol.In(["small", "medium", "large"]),
        vol.Exclusive("size_px", "cam_size"): vol.Schema(
            {
                vol.Required("w"): vol.All(
                    vol.Coerce(int), vol.Range(min=48, max=3840)
                ),
                vol.Required("h"): vol.All(
                    vol.Coerce(int), vol.Range(min=48, max=2160)
                ),
            }
        ),
        # Auto-hide in seconds: 0 = never, 15..300 otherwise
        vol.Optional("auto_hide", default=30): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=300)
        ),
        # Show title overlay?
        vol.Optional("show_title", default=True): cv.boolean,
        vol.Optional("device_id"): cv.string,
    }
)


class _Presence:
    """Zeroconf: track the app instance and keep host/port fresh."""

    def __init__(self, hass: HomeAssistant, entry: config_entries.ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._browser: AsyncServiceBrowser | None = None
        self._aiozc = None

    async def start(self) -> None:
        self._aiozc = await ha_zc.async_get_async_instance(self.hass)
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
        self.hass.async_create_task(
            self._handle_change(service_type, name, state_change)
        )

    async def _handle_change(
        self, service_type: str, name: str, state_change: ServiceStateChange
    ) -> None:
        if service_type != SERVICE_TYPE:
            return

        wanted_id = (self.entry.data.get("id") or "").strip().lower()

        if state_change is ServiceStateChange.Removed:
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

        host = (info.parsed_addresses() or [self.entry.data.get(CONF_HOST)])[0]
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
                    if ent.data.get("id") == ident or ent.entry_id == ident:
                        return ent
    if len(entries) == 1:
        return entries[0]
    return None  # ambiguous or none configured


async def _handle_quickbar(hass: HomeAssistant, call: ServiceCall) -> None:
    """Service handler for quickbar_toggle."""
    data: dict[str, Any] = {"alias": call.data["alias"]}
    target_device_id = call.data.get("device_id")
    if target_device_id:
        ent = _entry_for_device(hass, target_device_id)
        if ent:
            data["id"] = ent.data.get("id") or ent.entry_id
    hass.bus.async_fire(EVENT_NAME, data)


async def _handle_camera(hass: HomeAssistant, call: ServiceCall) -> None:
    """Service handler for camera_toggle."""
    data: dict[str, Any] = {}

    # optional device targeting
    target_device_id = call.data.get("device_id")
    if target_device_id:
        ent = _entry_for_device(hass, target_device_id)
        if ent:
            data["id"] = ent.data.get("id") or ent.entry_id

    # id/alias
    alias = call.data.get("camera_alias")
    entity = call.data.get("camera_entity")
    if alias:
        data["camera_alias"] = alias
    if entity:
        data["camera_entity"] = entity

    data["rtsp_url"] = call.data.get("rtsp_url")

    # options
    pos = call.data.get("position")
    if pos in POS_CHOICES:
        data["position"] = pos

    if "size" in call.data:
        data["size"] = call.data["size"]  # small|medium|large
    elif "size_px" in call.data:
        sp = call.data["size_px"] or {}
        try:
            w = int(sp.get("w"))
            h = int(sp.get("h"))
            if w > 0 and h > 0:
                data["size_px"] = {"w": w, "h": h}
        except (TypeError, ValueError):
            # ignore invalid size objects
            pass

    auto_hide = call.data.get("auto_hide")
    if isinstance(auto_hide, int):
        if auto_hide != 0 and auto_hide < 5:
            auto_hide = 5
        data["auto_hide"] = auto_hide

    show_title = call.data.get("show_title")
    if isinstance(show_title, bool):
        data["show_title"] = show_title

    hass.bus.async_fire(EVENT_NAME, data)


async def _svc_notify(hass: HomeAssistant, call: ServiceCall) -> None:
    """Service handler for notify."""
    target_device_id = call.data.get("device_id")
    entry2 = _entry_for_device(hass, target_device_id) if target_device_id else None

    payload = await build_notify_payload(hass, call.data)
    if entry2:
        payload["id"] = entry2.data.get("id") or entry2.entry_id

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
    hass.services.async_register(
        DOMAIN, "quickbar_toggle", partial(_handle_quickbar, hass), QUICKBAR_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "camera_toggle", partial(_handle_camera, hass), CAMERA_SCHEMA
    )
    # Note: no voluptuous schema for notify (by design)
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
        identifiers={(DOMAIN, entry.data.get("id") or entry.entry_id)},
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
        exp_id = entry.data.get("id") or entry.entry_id
        if data.get("id") and data.get("id") != exp_id:
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
    # Gentle reminder for the TV app
    persistent_notification.async_create(
        hass,
        (
            "The QuickBars integration for a specific TV was removed from Home Assistant.\n\n"
            "If the QuickBars TV app is still paired, open the app → Settings "
            "→ Manage HA Integration → Reset Pairing to clean up pairing on the TV."
        ),
        title="QuickBars integration removed",
    )
