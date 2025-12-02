from __future__ import annotations

import logging
import asyncio

from .ssl_utils import get_aiohttp_ssl

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import HomeAssistantError
from homeassistant.config_entries import ConfigEntry
from .models import ConnectSenseConfigEntry

_LOGGER = logging.getLogger(__name__)

from .const import (
    DOMAIN,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_CODE_REBOOT,
    SIGNAL_UPDATE,
)

def _service_from_string(s: str) -> tuple[str, str]:
    s = (s or "").strip()
    if "." in s:
        d, svc = s.split(".", 1)
        return d, svc
    return "notify", s or "notify"

async def async_setup_entry(hass: HomeAssistant, entry: ConnectSenseConfigEntry, async_add_entities):
    async_add_entities([RebooterRebootButton(hass, entry)])


class RebooterRebootButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Reboot Now"
    _attr_icon = "mdi:restart"
    _attr_should_poll = False
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        base_uid = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_uid}_reboot"

    @property
    def device_info(self) -> DeviceInfo:
        host = self.entry.data[CONF_HOST]
        uid = self.entry.unique_id or host
        return DeviceInfo(
            identifiers={(DOMAIN, uid)},
            name=self.entry.title or f"Rebooter Pro {uid}",
            manufacturer="Grid Connect",
            model="Rebooter Pro"
        )

    async def _resolve_actor_name(self) -> str | None:
        """Return the HA user's display name for this call, if any."""
        ctx = getattr(self, "_context", None)  # set by HA on service call
        user = None
        if ctx and getattr(ctx, "user_id", None):
            maybe_coro = self.hass.auth.async_get_user(ctx.user_id)
            user = await maybe_coro if asyncio.iscoroutine(maybe_coro) else maybe_coro
        return user.name if user else None

    async def _send_manual_reboot_notification(self):
        """Send 'Manual Reboot Triggered' push notification using integration options."""
        entry = self.entry
        opts = entry.options or {}
        if not opts.get(CONF_NOTIFY_ENABLED, True):
            return
        if not opts.get(CONF_NOTIFY_CODE_REBOOT, True):
            return
    
        service_str = opts.get(CONF_NOTIFY_SERVICE, "notify.notify")
        domain, service = _service_from_string(service_str)

        # derive serial from entry.unique_id if digits; otherwise fall back
        serial = None
        uid = (entry.unique_id or "").strip()
        if uid.isdigit():
            serial = uid
        
        device_name = f"Rebooter Pro {serial}" if serial else (entry.title or self.entry.data.get(CONF_HOST, "Rebooter Pro"))
        actor = await self._resolve_actor_name()
        via = f"Home Assistant — {actor}" if actor else "Home Assistant"
    
        payload = {
            "title": f"Rebooter Pro is REBOOTING",
            "message": f"{device_name} reboot requested via {via}",
        }
        try:
            await self.hass.services.async_call(domain, service, payload, blocking=False)
        except Exception:
            _LOGGER.exception("Failed to send manual reboot notification via %s.%s", domain, service)

    async def async_press(self) -> None:
        host = self.entry.data[CONF_HOST]
        base = f"https://{host}:443"

        session = async_get_clientsession(self.hass)
        ssl_ctx = await get_aiohttp_ssl(self.hass, self.entry)

        async with session.post(f"{base}/control", json={"outlet_reboot": True}, ssl=ssl_ctx, timeout=8) as r:
            text = await r.text()
            if r.status >= 400:
                raise HomeAssistantError(f"Device rejected reboot ({r.status}): {text[:200]}")
            _LOGGER.debug("Reboot command responded %s: %s", r.status, text[:300])
            
            # Optimistically set the outlet to ON in HA after a successful reboot command
            async_dispatcher_send(
                self.hass,
                f"{SIGNAL_UPDATE}_{self.entry.entry_id}",
                {"outlet_active": True}
            )
        
            # Send the static push notification now that we have a 2xx
            await self._send_manual_reboot_notification()
