"""Bosch Smart Home Camera — Light Platform (Gen2 only).

Creates native HA light entities for Gen2 cameras (Eyes Außenkamera II):
  - Top LED Light   — RGB color + brightness (oberes Licht, "tausende Farben")
  - Bottom LED Light — RGB color + brightness (unteres Licht, "tausende Farben")
  - Front Light     — color temperature + brightness (Frontlicht, kaltweiß↔warmweiß)

Gen2 lighting API: PUT /v11/video_inputs/{id}/lighting/switch
Each light group uses EITHER color (HEX #RRGGBB) OR whiteBalance (-1.0 to 1.0), never both.
When color is set, whiteBalance becomes null (color mode).
When whiteBalance is set, color becomes null (temperature mode).

Gen1 cameras use a different API (lighting_override) and are handled by switch.py instead.
"""

import asyncio
import logging
import time
from typing import Any, ClassVar

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CLOUD_API, DOMAIN, BoschCameraConfigEntry  # type: ignore[attr-defined]
from .cloud_ssl import async_get_bosch_cloud_session
from .guards import _warn_if_privacy_on

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = config_entry.runtime_data
    entities = []
    for cam_id in coordinator.data:
        cam_info = coordinator.data[cam_id].get("info", {})
        # Prefer cam_info hardwareVersion (live cloud data); fall back to the
        # persistent `_hw_version` store so a cold-start during a cloud outage
        # still creates the right entities for Outdoor II. `getattr` keeps the
        # test stubs that don't seed the `_hw_version` dict happy.
        _hw_cache = getattr(coordinator, "_hw_version", {}) or {}
        hw = cam_info.get("hardwareVersion") or _hw_cache.get(cam_id, "CAMERA")
        from .models import get_model_config

        if get_model_config(hw).generation >= 2:
            has_light = cam_info.get("featureSupport", {}).get("light", False)
            # ONLY Outdoor II has controllable lights (RGB top + bottom + color-
            # temp front spotlight). Indoor II has NO visible light hardware —
            # only the IR night-vision LEDs which are not user-controllable.
            # Bosch's API correctly reports `featureSupport.light=false` for it.
            # v12.5.0 mistakenly created a `BoschFrontLight` for Indoor II based
            # on the stale `number.*_helligkeit_*` entities that were left in
            # the registry from an older codepath — those numbers also never
            # worked. Reverted in v12.5.1; cleanup runs in async_setup_entry.
            if has_light:
                entities.append(BoschTopLedLight(coordinator, cam_id, config_entry))
                entities.append(BoschBottomLedLight(coordinator, cam_id, config_entry))
                entities.append(BoschFrontLight(coordinator, cam_id, config_entry))
    async_add_entities(entities, update_before_add=False)


class _BoschLightBase(CoordinatorEntity, LightEntity, RestoreEntity):  # type: ignore[misc]
    """Base class for Gen2 light entities.

    Inherits from RestoreEntity so `_last_color_hex`, `_last_brightness`,
    and `_last_white_balance` survive HA restarts — without this, after a
    restart the entity has no memory of the last user-picked color, and
    the card's color circles fall back to warm-white default.
    """

    _led_key: str = (
        ""  # "frontLightSettings", "topLedLightSettings", "bottomLedLightSettings"
    )
    _attr_has_entity_name = True

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._cam_id = cam_id
        self._entry = entry
        info = coordinator.data.get(cam_id, {}).get("info", {})
        self._cam_title = info.get("title", cam_id)
        self._model = info.get("hardwareVersion", "CAMERA")
        from .models import get_display_name

        self._model_name = get_display_name(self._model)
        self._fw = info.get("firmwareVersion", "")
        self._mac = info.get("macAddress", "")

        # Local state cache
        self._brightness: int = 0
        self._last_brightness: int = (
            100  # remember last non-zero brightness for restore on turn_on
        )
        self._color_hex: str | None = None
        self._last_color_hex: str | None = None  # None = user has never picked a color
        self._white_balance: float | None = None
        self._last_white_balance: float | None = -1.0
        self._is_on: bool = False

    async def async_added_to_hass(self) -> None:
        """Restore last-known color/brightness/whiteBalance across HA restarts."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.attributes is None:
            return
        # Prefer the extra attribute we wrote ourselves (kept when light is off)
        lrc = last_state.attributes.get("last_rgb_color")
        if isinstance(lrc, (list, tuple)) and len(lrc) == 3:
            try:
                r, g, b = (int(lrc[0]), int(lrc[1]), int(lrc[2]))
                self._last_color_hex = f"#{r:02X}{g:02X}{b:02X}"
            except (ValueError, TypeError):
                pass
        lbri = last_state.attributes.get("last_brightness_pct")
        if isinstance(lbri, (int, float)) and 1 <= lbri <= 100:
            self._last_brightness = int(lbri)
        lwb = last_state.attributes.get("last_white_balance")
        if isinstance(lwb, (int, float)) and -1.0 <= lwb <= 1.0:
            self._last_white_balance = float(lwb)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose last-known values even when the light is off.

        HA's light platform blanks `rgb_color` / `brightness` when state=="off",
        so the Lovelace card can't read them to show the last user-picked
        color on the color circle. These extra attributes stay populated
        regardless of on/off state.
        """
        attrs: dict[str, Any] = {}
        color_hex = self._color_hex or self._last_color_hex
        if color_hex:
            h = color_hex.lstrip("#")
            try:
                attrs["last_rgb_color"] = [
                    int(h[0:2], 16),
                    int(h[2:4], 16),
                    int(h[4:6], 16),
                ]
            except ValueError:
                pass
        else:
            # Display-only warm-white default so the card's color dot isn't
            # grey before the user has ever picked a color. Never written to
            # the API — the turn_on fallback sends `color: null` instead so
            # the camera keeps its own default.
            attrs["last_rgb_color"] = [255, 180, 100]
        if self._last_brightness:
            attrs["last_brightness_pct"] = self._last_brightness
        if self._last_white_balance is not None:
            attrs["last_white_balance"] = self._last_white_balance
        return attrs

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._cam_id)},
            "name": f"Bosch {self._cam_title}",
            "manufacturer": "Bosch",
            "model": self._model_name,
            "sw_version": self._fw,
            "connections": {("mac", self._mac)} if self._mac else set(),
        }

    @property
    def is_on(self) -> bool:
        self._load_state_from_cache()
        return self._is_on

    @property
    def brightness(self) -> int | None:
        """HA brightness is 0-255, API brightness is 0-100.

        When off, return last brightness so the UI slider keeps its position.
        """
        self._load_state_from_cache()
        if self._is_on:
            return int(self._brightness * 255 / 100) if self._brightness else 0
        return int(self._last_brightness * 255 / 100) if self._last_brightness else None

    @property
    def available(self) -> bool:
        """Cloud-primary with LAN-reachability fallback (Gen2 only).

        When the Bosch cloud is unreachable but the camera is pingable on
        the LAN, the coordinator's set-light path will fall through to a
        direct RCP write — so the entity must remain controllable. Without
        this fallback, every Bosch cloud 5xx leaves the light entities grey
        even though they are toggleable on the same LAN via the Bosch app.

        Exception: during a firmware install the camera reboots — writes
        would fail mid-flight, so flip unavailable until the slow-tier poll
        clears the `updating` flag.
        """
        is_updating = getattr(self.coordinator, "is_updating", None)
        if is_updating is not None and is_updating(self._cam_id):
            return False
        if self.coordinator.last_update_success:
            return True
        is_lan_reachable = getattr(self.coordinator, "is_lan_reachable", None)
        if is_lan_reachable is None:
            return False
        if not bool(is_lan_reachable(self._cam_id)):
            return False
        # See switch.py BoschPrivacyModeSwitch.available — same relaxation:
        # if hw_version isn't yet known (cold-start during cloud outage),
        # allow the toggle. The write fails cleanly for Gen1.
        from .shc import _is_gen2

        if _is_gen2(self.coordinator, self._cam_id):
            return True
        hw = self.coordinator._hw_version.get(self._cam_id)
        return hw in (None, "", "CAMERA")

    def _load_state_from_cache(self) -> None:
        """Sync state from coordinator lighting/switch cache.

        Called on every property access so HA reflects changes made via the
        Bosch app (polled by the coordinator).  Remembers last non-zero
        brightness and last color for restore-on-turn-on.
        """
        lsc = self.coordinator._lighting_switch_cache.get(self._cam_id, {})
        if not lsc:
            return
        led = lsc.get(self._led_key, {})
        bri = led.get("brightness", 0)
        color = led.get("color")
        wb = led.get("whiteBalance")
        self._brightness = bri
        self._is_on = bri > 0
        if bri > 0:
            self._last_brightness = bri
        if color:
            self._color_hex = color
            self._last_color_hex = color
            self._white_balance = None
        elif wb is not None:
            self._white_balance = wb
            self._last_white_balance = wb
            self._color_hex = None

    def _get_current_state(self) -> dict[str, Any]:
        """Get the current lighting/switch state from coordinator cache."""
        cached = self.coordinator._lighting_switch_cache.get(self._cam_id, {})
        # Default fallback if cache is empty
        return {
            "frontLightSettings": cached.get(
                "frontLightSettings",
                {"brightness": 0, "color": None, "whiteBalance": -1.0},
            ),
            "topLedLightSettings": cached.get(
                "topLedLightSettings",
                {"brightness": 0, "color": None, "whiteBalance": -1.0},
            ),
            "bottomLedLightSettings": cached.get(
                "bottomLedLightSettings",
                {"brightness": 0, "color": None, "whiteBalance": -1.0},
            ),
        }

    async def _put_lighting_switch(self, updates: dict[str, Any]) -> bool:
        """Send PUT /lighting/switch — ALWAYS sends full body with all 3 groups.

        The Bosch API requires all 3 light groups in every PUT request.
        `updates` contains only the keys to change; the rest is read from cache.
        """
        token = self.coordinator.token
        if not token:
            return False
        # Serialize the read-modify-write per camera. /lighting/switch REQUIRES
        # the full 3-group body in every PUT, so two concurrent sibling writes
        # (e.g. a scene toggling Top + Bottom LED, or Front + white-balance) that
        # each build their body from a pre-write cache snapshot would each
        # re-send the OTHER group's stale value — reverting it both in the cache
        # AND on the actual camera. The lock makes each write build its body from
        # a cache that already contains the prior write's result, and we merge
        # only the changed group(s) back (never the whole entry). Matches the
        # merge-only-own-key fix number.py already got in 2026-06-02.
        # (bug-hunt 2026-07-01)
        locks = getattr(self.coordinator, "_lighting_switch_locks", None)
        if locks is None:
            locks = {}
            self.coordinator._lighting_switch_locks = locks
        lock = locks.get(self._cam_id)
        if lock is None:
            lock = asyncio.Lock()
            locks[self._cam_id] = lock
        async with lock:
            # Build full body INSIDE the lock so it reflects any sibling write
            # that just completed.
            body = self._get_current_state()
            for key, val in updates.items():
                if key in body:
                    body[key] = {**body[key], **val}  # merge, not replace
                else:
                    body[key] = val
            session = await async_get_bosch_cloud_session(self.hass)
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            try:
                async with asyncio.timeout(10):
                    async with session.put(
                        f"{CLOUD_API}/v11/video_inputs/{self._cam_id}/lighting/switch",
                        headers=headers,
                        json=body,
                    ) as resp:
                        if resp.status in (200, 201, 204):
                            # /lighting/switch returns 204 No Content (empty body);
                            # 200/201 would carry authoritative JSON. Prefer the
                            # server body when present, else the optimistic `body`
                            # we sent. (BUG-FIX 2026-05-28: the old resp.json() on a
                            # 204 raised → swallowed → cache never updated → is_on
                            # stuck False.)
                            try:
                                rsp = await resp.json(content_type=None)
                            except Exception:
                                rsp = None
                            authoritative = (
                                rsp if (rsp and isinstance(rsp, dict)) else body
                            )
                            # Merge ONLY the group(s) we changed into the live
                            # cache — never overwrite the whole entry, or a sibling
                            # group written concurrently would be clobbered.
                            cur = self.coordinator._lighting_switch_cache.setdefault(
                                self._cam_id, {}
                            )
                            for key in updates:
                                if key in authoritative:
                                    cur[key] = authoritative[key]
                            return True
                        _LOGGER.warning(
                            "lighting/switch HTTP %d for %s",
                            resp.status,
                            self._cam_id[:8],
                        )
            except Exception as err:
                _LOGGER.warning(
                    "lighting/switch error for %s: %s", self._cam_id[:8], err
                )
            return False

    async def _put_switch_endpoint(self, endpoint: str, enabled: bool) -> bool:
        """Send PUT /lighting/switch/front or /topdown."""
        token = self.coordinator.token
        if not token:
            return False
        session = await async_get_bosch_cloud_session(self.hass)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            async with asyncio.timeout(10):
                async with session.put(
                    f"{CLOUD_API}/v11/video_inputs/{self._cam_id}/lighting/switch/{endpoint}",
                    headers=headers,
                    json={"enabled": enabled},
                ) as resp:
                    return resp.status in (200, 201, 204)
        except Exception as err:
            _LOGGER.warning("lighting/switch/%s error: %s", endpoint, err)
        return False


# ─────────────────────────────────────────────────────────────────────────────
class _BoschRgbLedLight(_BoschLightBase):
    """Base for Top/Bottom LED light — RGB color + brightness.

    Remembers last brightness and color for restore on turn_on.
    """

    _led_key = ""
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes: ClassVar[set[ColorMode]] = {ColorMode.RGB}

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        self._load_state_from_cache()
        color = self._color_hex or self._last_color_hex
        if color:
            h = color.lstrip("#")
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        # Default warm white when no color known (e.g. after HA restart with light off)
        return (255, 180, 100)

    def _sync_wallwasher_cache(self) -> None:
        """Sync wallwasher switch state from lighting/switch cache.

        Called after light entity turn_on/turn_off to immediately update the
        wallwasher switch without waiting for the next coordinator poll.
        """
        lsc = self.coordinator._lighting_switch_cache.get(self._cam_id, {})
        top_bri = lsc.get("topLedLightSettings", {}).get("brightness", 0)
        bot_bri = lsc.get("bottomLedLightSettings", {}).get("brightness", 0)
        front_bri = lsc.get("frontLightSettings", {}).get("brightness", 0)
        cache_entry = self.coordinator._shc_state_cache.setdefault(self._cam_id, {})
        cache_entry["wallwasher"] = top_bri > 0 or bot_bri > 0
        cache_entry["camera_light"] = front_bri > 0 or top_bri > 0 or bot_bri > 0
        self.coordinator._light_set_at[self._cam_id] = time.monotonic()
        self.coordinator.async_update_listeners()

    async def async_turn_on(self, **kwargs: Any) -> None:
        # Privacy mode blocks /lighting/switch PUT with HTTP 443 — warn the user.
        if await _warn_if_privacy_on(self, "RGB Light"):
            return
        self._load_state_from_cache()
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        rgb = kwargs.get(ATTR_RGB_COLOR)
        was_off = not self._is_on
        color_hex: str | None = None

        if rgb:
            color_hex = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
            self._color_hex = color_hex
            self._last_color_hex = color_hex
            self._white_balance = None
        else:
            # Restore last color (may be None if user has never picked a color)
            color_hex = self._color_hex or self._last_color_hex

        if brightness:
            # Round up so brightness=1 (card sentinel for "at least 1 step")
            # doesn't collapse to 0% and skip the last_brightness_pct attribute.
            self._last_brightness = max(1, round(brightness * 100 / 255))

        # Preconfigure while off: any color/brightness change is stored locally
        # but the light stays physically off. User must explicitly toggle the
        # switch row (turn_on with no kwargs) to apply the stored settings.
        if was_off and (rgb or brightness):
            self.async_write_ha_state()
            return

        # Restore last brightness if not specified
        api_brightness = (
            max(1, round(brightness * 100 / 255))
            if brightness
            else (self._last_brightness or 100)
        )

        if color_hex:
            body = {
                self._led_key: {
                    "brightness": api_brightness,
                    "color": color_hex,
                    "whiteBalance": None,
                }
            }
        else:
            body = {
                self._led_key: {
                    "brightness": api_brightness,
                    "color": None,
                    "whiteBalance": -1.0,
                }
            }

        # Only commit the optimistic on-state if the PUT actually succeeded —
        # otherwise is_on/brightness (raw instance vars) would show the light ON
        # after a failed write until the next slow poll corrects it.
        if await self._put_lighting_switch(body):
            self._brightness = api_brightness
            self._last_brightness = api_brightness
            self._is_on = True
            await self._put_switch_endpoint("topdown", True)
        self._sync_wallwasher_cache()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Remember current settings before turning off
        if self._brightness > 0:
            self._last_brightness = self._brightness
        if self._color_hex:
            self._last_color_hex = self._color_hex
        body = {self._led_key: {"brightness": 0}}
        if await self._put_lighting_switch(body):
            self._is_on = False
            self._brightness = 0
            # If BOTH top+bottom are now off, also disable topdown switch
            lsc = self.coordinator._lighting_switch_cache.get(self._cam_id, {})
            top_bri = lsc.get("topLedLightSettings", {}).get("brightness", 0)
            bot_bri = lsc.get("bottomLedLightSettings", {}).get("brightness", 0)
            if top_bri == 0 and bot_bri == 0:
                await self._put_switch_endpoint("topdown", False)
        self._sync_wallwasher_cache()
        self.async_write_ha_state()


class BoschTopLedLight(_BoschRgbLedLight):
    """Light entity: Top LED (oberes Licht) — RGB color + brightness."""

    _led_key = "topLedLightSettings"

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_top_led_light"
        self._attr_translation_key = "top_led_light"


# ─────────────────────────────────────────────────────────────────────────────
class BoschBottomLedLight(_BoschRgbLedLight):
    """Light entity: Bottom LED (unteres Licht) — RGB color + brightness."""

    _led_key = "bottomLedLightSettings"

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_bottom_led_light"
        self._attr_translation_key = "bottom_led_light"


# ─────────────────────────────────────────────────────────────────────────────
class BoschFrontLight(_BoschLightBase):
    """Light entity: Front spotlight — color temperature + brightness.

    Front light only supports white with color temperature (whiteBalance -1.0 to 1.0),
    NOT RGB colors. -1.0 = cool/blue, 0.0 = neutral, 1.0 = warm/orange.
    Mapped to HA color temp: 2000K (warm) to 6500K (cool).
    """

    _led_key = "frontLightSettings"
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_supported_color_modes: ClassVar[set[ColorMode]] = {ColorMode.COLOR_TEMP}
    _attr_min_color_temp_kelvin = 2000
    _attr_max_color_temp_kelvin = 6500

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_front_light_entity"
        self._attr_translation_key = "front_light_entity"
        self._white_balance = -1.0

    @property
    def color_temp_kelvin(self) -> int | None:
        """Convert whiteBalance (-1.0 to 1.0) to Kelvin (6500 to 2000).

        When off, return last value so the UI slider keeps its position.
        """
        self._load_state_from_cache()
        wb = self._white_balance
        if wb is None:
            wb = (
                self._last_white_balance
                if self._last_white_balance is not None
                else -1.0
            )
        # -1.0 (cool) = 6500K, 1.0 (warm) = 2000K
        return int(4250 - wb * 2250)

    async def async_turn_on(self, **kwargs: Any) -> None:
        # Privacy mode blocks /lighting/switch PUT with HTTP 443 — warn the user.
        if await _warn_if_privacy_on(self, "Front Light"):
            return
        self._load_state_from_cache()
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_k = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        was_off = not self._is_on

        if color_temp_k:
            # Convert Kelvin to whiteBalance: 6500K = -1.0, 2000K = 1.0
            wb = round((4250 - color_temp_k) / 2250, 2)
            wb = max(-1.0, min(1.0, wb))
            self._white_balance = wb
            self._last_white_balance = wb
        else:
            wb = self._white_balance if self._white_balance is not None else -1.0

        if brightness:
            self._last_brightness = max(1, round(brightness * 100 / 255))

        # Preconfigure while off: any change is stored locally, light stays off.
        # User must explicitly toggle the switch row to apply the stored values.
        if was_off and (brightness or color_temp_k):
            self.async_write_ha_state()
            return

        api_brightness = (
            max(1, round(brightness * 100 / 255))
            if brightness
            else (self._last_brightness or 100)
        )

        body = {
            self._led_key: {
                "brightness": api_brightness,
                "color": None,
                "whiteBalance": wb,
            }
        }
        if await self._put_lighting_switch(body):
            self._brightness = api_brightness
            self._last_brightness = api_brightness
            self._is_on = True
            await self._put_switch_endpoint("front", True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Send brightness=0 to update cache + camera state (like the Bosch app does),
        # then disable via switch endpoint. Without the PUT, the cache retains the old
        # brightness, and any subsequent top/bottom LED PUT would re-enable the front light.
        # Only commit the optimistic off-state if the PUT succeeded.
        wb = self._white_balance if self._white_balance is not None else -1.0
        if await self._put_lighting_switch(
            {self._led_key: {"brightness": 0, "color": None, "whiteBalance": wb}}
        ):
            self._is_on = False
            self._brightness = 0
            await self._put_switch_endpoint("front", False)
        self.async_write_ha_state()
