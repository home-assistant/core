from __future__ import annotations

import logging
import asyncio
import ssl
import aiohttp

from datetime import timedelta
from typing import Any


from homeassistant.util import dt as dt_util
from homeassistant.auth.models import User
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import CONF_HOST
from homeassistant.config_entries import ConfigEntry

from .models import ConnectSenseConfigEntry

from .const import (
    DOMAIN,
    SIGNAL_UPDATE,
    CONF_AR_POWER_FAIL,
    CONF_AR_PING_FAIL,
    DEFAULT_AR_POWER_FAIL,
    DEFAULT_AR_PING_FAIL,
)
from .ssl_utils import get_aiohttp_ssl

_LOGGER = logging.getLogger(__name__)
MUTE_SECONDS = 8

async def async_setup_entry(hass: HomeAssistant, entry: ConnectSenseConfigEntry, async_add_entities):
    """Set up all Rebooter Pro switches from a config entry."""
    entities: list[SwitchEntity] = [
        RebooterOutletSwitch(hass, entry),
        RebooterPowerFailSwitch(hass, entry),
        RebooterPingFailSwitch(hass, entry),
    ]
    async_add_entities(entities)


class RebooterOutletSwitch(SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Toggle Power"
    _attr_should_poll = False
    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self._is_on = None
        self._unsub = None
        self._confirm_task = None
        self._cmd_lock = asyncio.Lock()
        base_uid = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_uid}_outlet"

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

    @property
    def is_on(self) -> bool | None:
        return self._is_on

    @property
    def available(self) -> bool:
        # You could add smarter availability later; for now assume reachable.
        return True

    @property
    def extra_state_attributes(self):
        state = self.hass.data[DOMAIN][self.entry.entry_id]["state"]
        last = state.get("last_event") or {}
        rebooting = state.get("rebooting")
        attrs = {}
        if last:
            attrs["last_event_code"] = last.get("code")
            attrs["last_event_source"] = last.get("source")
            attrs["last_event_message"] = last.get("message")
            attrs["last_event_device"] = last.get("device")
            attrs["last_event_ts"] = last.get("timestamp")
        if rebooting is not None:
            attrs["rebooting"] = rebooting
        return attrs

    async def _resolve_actor_name(self) -> str | None:
        """Return the HA user's display name for this call, if any."""
        ctx = getattr(self, "_context", None)  # set by HA on service call
        user = None
        if ctx and getattr(ctx, "user_id", None):
            maybe_coro = self.hass.auth.async_get_user(ctx.user_id)
            user = await maybe_coro if asyncio.iscoroutine(maybe_coro) else maybe_coro
        return user.name if user else None


    async def async_added_to_hass(self):
        # Listen for webhook-driven updates
        self._unsub = async_dispatcher_connect(
            self.hass,
            f"{SIGNAL_UPDATE}_{self.entry.entry_id}",
            self._handle_push,
        )

        # One-shot seed: fetch current outlet state via GET /control
        # Run as a background task so we don't block entity setup.
        self.hass.async_create_task(self._fetch_initial_state())

    async def async_will_remove_from_hass(self):
        if self._unsub:
            self._unsub()
            self._unsub = None
        if self._confirm_task and not self._confirm_task.done():
            self._confirm_task.cancel()
            self._confirm_task = None

    def _handle_push(self, payload: dict):
        # Update from webhook
        if "outlet_active" in payload:
            self._is_on = bool(payload["outlet_active"])
            _LOGGER.debug("Push update -> outlet_active=%s", self._is_on)
        self.schedule_update_ha_state()

    async def _fetch_initial_state(self):
        host = self.entry.data[CONF_HOST]
        base = f"https://{host}:443"

        ssl_ctx = await get_aiohttp_ssl(self.hass, self.entry)
        session = async_get_clientsession(self.hass)

        try:
            async with session.get(f"{base}/control", ssl=ssl_ctx, timeout=8) as r:
                data = await r.json(content_type=None)
                if isinstance(data, dict) and "outlet_active" in data:
                    self._is_on = bool(data["outlet_active"])
                    _LOGGER.debug("Seeded initial outlet_active=%s from GET /control", self._is_on)
                    self.async_write_ha_state()
                else:
                    _LOGGER.debug("GET /control returned unexpected payload: %s", data)
        except Exception as exc:
            _LOGGER.debug("Initial GET /control failed (%s); leaving state unknown", exc)

    async def async_turn_on(self, **kwargs):
        await self._send_with_optimistic_state(True)

    async def async_turn_off(self, **kwargs):
        await self._send_with_optimistic_state(False)

    async def _send_with_optimistic_state(self, desired_on: bool):
        """Flip UI immediately; revert if POST fails."""
        prev = self._is_on
        self._is_on = desired_on
        self.async_write_ha_state()

        try:
            async with self._cmd_lock:  # prevent overlapping POSTs
                await self._post_control({"outlet_active": desired_on})
        except HomeAssistantError:
            # Revert UI
            self._is_on = prev
            self.async_write_ha_state()
            raise  # let the friendly error bubble to the UI

    async def _post_control(self, body: dict):
        host = self.entry.data[CONF_HOST]
        base = f"https://{host}:443"

        ssl_ctx = await get_aiohttp_ssl(self.hass, self.entry)
        session = async_get_clientsession(self.hass)

        _LOGGER.debug("POST /control -> %s", body)
        try:
            store = self.hass.data[DOMAIN].setdefault(self.entry.entry_id, {})
            # store the last actor for incoming notification
            actor = await self._resolve_actor_name()
            if actor:
                store["last_actor"] = actor
            
            # Start/extend the mute window so codes 1/2 webhooks are ignored briefly
            store["mute_until"] = dt_util.utcnow() + timedelta(seconds=MUTE_SECONDS)    
                    
            async with session.post(
                f"{base}/control", json=body, ssl=ssl_ctx, timeout=8
            ) as r:
                text = await r.text()
                if r.status >= 400:
                    # Convert device/server errors into a clean HA error with a short message
                    raise HomeAssistantError(f"Device rejected command ({r.status}): {text[:200]}")
                _LOGGER.debug("Device responded %s: %s", r.status, text[:300])

                # Re-schedule a single confirmation fetch at window end
                if self._confirm_task and not self._confirm_task.done():
                    self._confirm_task.cancel()
                self._confirm_task = self.hass.async_create_task(self._confirm_after_timeout())


        except asyncio.TimeoutError as e:
            store = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
            if store:
                store.pop("last_actor", None)
                store.pop("mute_until", None)
            _LOGGER.warning("Rebooter Pro: command timed out after 8s")
            raise HomeAssistantError("Rebooter Pro didn’t respond in time (8s).") from e

        except aiohttp.ClientConnectorError as e:
            store = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
            if store:
                store.pop("last_actor", None)
                store.pop("mute_until", None)
            _LOGGER.warning("Rebooter Pro: network error: %s", e)
            raise HomeAssistantError("Network error talking to Rebooter Pro.") from e

        except aiohttp.ClientError as e:
            store = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
            if store:
                store.pop("last_actor", None)
                store.pop("mute_until", None)
            _LOGGER.warning("Rebooter Pro: HTTP error: %s", e)
            raise HomeAssistantError("HTTP error talking to Rebooter Pro.") from e

        except ssl.SSLError as e:
            store = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
            if store:
                store.pop("last_actor", None)
                store.pop("mute_until", None)
            _LOGGER.warning("Rebooter Pro: SSL error (certificate/hostname): %s", e)
            raise HomeAssistantError("SSL error (certificate/hostname mismatch).") from e

        except asyncio.CancelledError:
            store = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
            if store:
                store.pop("last_actor", None)
                store.pop("mute_until", None)
            _LOGGER.debug("Rebooter Pro: command cancelled")
            raise HomeAssistantError("Command cancelled.")

    async def _confirm_after_timeout(self):
        try:
            await asyncio.sleep(MUTE_SECONDS)
        except asyncio.CancelledError:
            return
        
        # Clear the last actor and stale mute flag, then reconcile state once.
        _LOGGER.debug("Rebooter Pro: clearing last actor")
        store = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
        if store is not None:
            store.pop("last_actor", None)
            store.pop("mute_until", None)
        
        # One-shot reconciliation after the mute window
        await self._fetch_initial_state()
        

# ------------------- Config flags (power-fail / ping-fail) --------------------
class _RebooterConfigFlagSwitch(SwitchEntity):
    """Base class for config flag toggles that POST partial /config and update options."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG


    # to override in subclasses:
    _flag_key_store: str = ""       # key in hass.data[DOMAIN][entry_id]["state"]
    _option_key: str = ""           # key in entry.options
    _device_field: str = ""         # field name posted to /config

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        base_uid = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_uid}_{self._flag_key_store}"
        # seed from in-memory state first; fall back to options/defaults if missing
        state_bucket = hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {}).setdefault("state", {})
        if self._flag_key_store in state_bucket:
            self._is_on = bool(state_bucket[self._flag_key_store])
        else:
            opts = entry.options or {}
            default_val = (
                DEFAULT_AR_POWER_FAIL if self._option_key == CONF_AR_POWER_FAIL
                else DEFAULT_AR_PING_FAIL
            )
            self._is_on = bool(opts.get(self._option_key, default_val))
        self._unsub = None

    @property
    def device_info(self) -> DeviceInfo:
        host = self.entry.data[CONF_HOST]
        uid = self.entry.unique_id or host
        return DeviceInfo(
            identifiers={(DOMAIN, uid)},
            name=self.entry.title or f"Rebooter Pro {uid}",
            manufacturer="Grid Connect",
            model="Rebooter Pro",
        )

    @property
    def is_on(self) -> bool | None:
        return self._is_on

    async def async_added_to_hass(self) -> None:
        @callback
        def _handle_update(payload: dict) -> None:
            if self._flag_key_store in payload:
                new_val = bool(payload[self._flag_key_store])
                if new_val != self._is_on:
                    self._is_on = new_val
                    self.schedule_update_ha_state()

        self._unsub = async_dispatcher_connect(
            self.hass,
            f"{SIGNAL_UPDATE}_{self.entry.entry_id}",
            _handle_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_flag(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_flag(False)

    async def _set_flag(self, desired: bool) -> None:
        """POST partial /config and update options to reflect the new flag."""
        prev = self._is_on
        self._is_on = desired
        self.async_write_ha_state()

        host = self.entry.data[CONF_HOST]
        base = f"https://{host}:443"
        ssl_ctx = await get_aiohttp_ssl(self.hass, self.entry)
        session = async_get_clientsession(self.hass)

        payload = {self._device_field: desired}
        _LOGGER.debug("POST /config partial -> %s", payload)

        try:
            async with session.post(
                f"{base}/config", json=payload, ssl=ssl_ctx, timeout=8
            ) as r:
                text = await r.text()
                if r.status >= 400:
                    raise HomeAssistantError(
                        f"Device rejected config ({r.status}): {text[:200]}"
                    )
                _LOGGER.debug("Partial config applied %s: %s", r.status, text[:300])

            # Update HA options to match (this will trigger your options listener)
            new_opts = dict(self.entry.options or {})
            new_opts[self._option_key] = desired
            self.hass.config_entries.async_update_entry(self.entry, options=new_opts)

            # Update in-memory state immediately and notify listeners
            store = self.hass.data.setdefault(DOMAIN, {}).setdefault(self.entry.entry_id, {})
            state = store.setdefault("state", {})
            state[self._flag_key_store] = desired
            async_dispatcher_send(
                self.hass,
                f"{SIGNAL_UPDATE}_{self.entry.entry_id}",
                {self._flag_key_store: desired},
            )

        except Exception as e:
            # Revert UI on any error
            self._is_on = prev
            self.async_write_ha_state()
            raise

# Power-fail auto-reboot toggle
class RebooterPowerFailSwitch(_RebooterConfigFlagSwitch):
    _attr_name = "Power Outage Auto Reboot"
    _flag_key_store = "pf_enabled"
    _option_key = CONF_AR_POWER_FAIL
    _device_field = "enable_power_fail_reboot"


# Ping-fail auto-reboot toggle
class RebooterPingFailSwitch(_RebooterConfigFlagSwitch):
    _attr_name = "Intelligent Reboot"
    _flag_key_store = "ping_enabled"
    _option_key = CONF_AR_PING_FAIL
    _device_field = "enable_ping_fail_reboot"
        
