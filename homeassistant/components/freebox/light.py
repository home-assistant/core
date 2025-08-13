"""Support for Freebox LED strip."""

from __future__ import annotations

import json
import logging
from typing import Any

from freebox_api.exceptions import HttpRequestError, InsufficientPermissionsError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .router import FreeboxConfigEntry, FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Freebox LED strip light."""
    router = entry.runtime_data

    _LOGGER.debug(
        "[freebox.light] Starting setup for router name=%s mac=%s",
        getattr(router, "name", "unknown"),
        getattr(router, "mac", "unknown"),
    )

    # Ensure lcd_config is fetched from the API before checks
    await router.update_lcd_config()

    # Log the LCD config for diagnostics
    lcd_config = getattr(router, "lcd_config", None)
    if not router or not lcd_config or not isinstance(lcd_config, dict):
        try:
            router_json = json.dumps(
                {
                    "name": getattr(router, "name", None),
                    "mac": getattr(router, "mac", None),
                    "lcd_config": lcd_config,
                },
                default=str,
                indent=2,
            )
        except (TypeError, ValueError) as err:
            router_json = f"<failed to serialize router: {err}>"

        _LOGGER.warning(
            "[freebox.light] No valid lcd_config found on router '%s' (mac=%s); LED strip entity will not be created. Router object: %s",
            getattr(router, "name", "unknown"),
            getattr(router, "mac", "unknown"),
            router_json,
        )
        return

    _log_lcd_config_diagnostics(router.lcd_config)

    # Check if the router has LCD configuration with LED strip attributes
    if not _has_led_strip_support(router.lcd_config):
        missing = _missing_led_attrs(router.lcd_config)
        _LOGGER.warning(
            "[freebox.light] LED strip not supported for router '%s' (mac=%s). "
            "Missing attributes: %s; keys=%s",
            getattr(router, "name", "unknown"),
            getattr(router, "mac", "unknown"),
            missing,
            list(router.lcd_config.keys())
            if isinstance(router.lcd_config, dict)
            else "not dict",
        )
        return

    async_add_entities([FreeboxLEDStripLight(router)], True)
    _LOGGER.info(
        "[freebox.light] LED strip entity scheduled for addition for router '%s' (mac=%s)",
        getattr(router, "name", "unknown"),
        getattr(router, "mac", "unknown"),
    )


def _has_led_strip_support(lcd_config: dict[str, Any]) -> bool:
    """Check if LCD config contains LED strip attributes."""
    if not lcd_config or not isinstance(lcd_config, dict):
        return False

    return len(_missing_led_attrs(lcd_config)) == 0


def _missing_led_attrs(lcd_config: dict[str, Any]) -> list[str]:
    """Return list of missing LED strip attributes in lcd_config."""
    required_attributes = [
        "led_strip_enabled",
        "led_strip_brightness",
        "led_strip_animation",
        "available_led_strip_animations",
    ]
    if not isinstance(lcd_config, dict):
        return required_attributes
    return [attr for attr in required_attributes if attr not in lcd_config]


def _log_lcd_config_diagnostics(lcd_config: dict[str, Any]) -> None:
    """Log detailed diagnostics about the lcd_config for troubleshooting."""
    config_type = type(lcd_config).__name__
    keys = list(lcd_config.keys()) if isinstance(lcd_config, dict) else None
    missing = _missing_led_attrs(lcd_config)

    _LOGGER.debug(
        "[freebox.light] lcd_config: type=%s, keys=%s, missing_required=%s",
        config_type,
        keys,
        missing,
    )


def _create_permission_repair_issue(hass: HomeAssistant, router_mac: str) -> None:
    """Create a repair issue for insufficient permissions."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"led_strip_permissions_{router_mac}",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="led_strip_permissions",
        translation_placeholders={"mac": router_mac},
    )


def _dismiss_permission_repair_issue(hass: HomeAssistant, router_mac: str) -> None:
    """Dismiss the permission repair issue when permissions are working."""
    ir.async_delete_issue(hass, DOMAIN, f"led_strip_permissions_{router_mac}")


class FreeboxLEDStripLight(LightEntity):
    """Representation of the Freebox LED strip light."""

    _attr_has_entity_name = True
    _attr_translation_key = "led_strip"
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, router: FreeboxRouter) -> None:
        """Initialize the Freebox LED strip light."""
        self._router = router
        self._attr_unique_id = f"{router.mac}-led_strip"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, router.mac)},
            manufacturer="Freebox SAS",
            name=router.name,
            model=router.name,
        )

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_lcd_update,
                self.async_write_ha_state,
            )
        )

    @property
    def is_on(self) -> bool:
        """Return if the light is on."""
        if not _has_led_strip_support(self._router.lcd_config):
            return False
        return self._router.lcd_config.get("led_strip_enabled", False)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if not self.is_on or not _has_led_strip_support(self._router.lcd_config):
            return None

        brightness_pct = self._router.lcd_config.get("led_strip_brightness", 100)
        # Convert from 0-100 to 0-255
        return int((brightness_pct / 100) * 255)

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        if not self.is_on or not _has_led_strip_support(self._router.lcd_config):
            return None
        return self._router.lcd_config.get("led_strip_animation")

    @property
    def effect_list(self) -> list[str] | None:
        """Return list of available effects."""
        if not _has_led_strip_support(self._router.lcd_config):
            return None
        return self._router.lcd_config.get("available_led_strip_animations")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if not _has_led_strip_support(self._router.lcd_config):
            _LOGGER.warning("LED strip not supported on this Freebox model")
            return

        # Build config with only values to change
        config: dict[str, Any] = {"led_strip_enabled": True}

        # Handle brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness_255 = kwargs[ATTR_BRIGHTNESS]
            if isinstance(brightness_255, (int, float)):
                # Convert from 0-255 to 0-100
                brightness_pct = int((brightness_255 / 255) * 100)
                config["led_strip_brightness"] = brightness_pct

        # Handle effect
        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            available_effects = self._router.lcd_config.get(
                "available_led_strip_animations", []
            )
            if effect in available_effects:
                config["led_strip_animation"] = effect
            else:
                _LOGGER.warning(
                    "Effect %s is not available. Available effects: %s",
                    effect,
                    available_effects,
                )

        # Send the configuration (only this part can raise exceptions)
        try:
            await self._router.set_lcd_config(config)
        except InsufficientPermissionsError:
            _LOGGER.warning(
                "Insufficient permissions to control LED strip. Please grant 'Modification des réglages de la Freebox' permission in Freebox settings"
            )
            _create_permission_repair_issue(self.hass, self._router.mac)
            return
        except HttpRequestError as err:
            _LOGGER.error("Failed to turn on LED strip: %s", err)
            return

        # Dismiss any existing permission repair issue on success
        _dismiss_permission_repair_issue(self.hass, self._router.mac)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if not _has_led_strip_support(self._router.lcd_config):
            _LOGGER.warning("LED strip not supported on this Freebox model")
            return

        # Send only the value to change (only this part can raise exceptions)
        config: dict[str, Any] = {"led_strip_enabled": False}
        try:
            await self._router.set_lcd_config(config)
        except InsufficientPermissionsError:
            _LOGGER.warning(
                "Insufficient permissions to control LED strip. Please grant 'Modification des réglages de la Freebox' permission in Freebox settings"
            )
            _create_permission_repair_issue(self.hass, self._router.mac)
            return
        except HttpRequestError as err:
            _LOGGER.error("Failed to turn off LED strip: %s", err)
            return

        # Dismiss any existing permission repair issue on success
        _dismiss_permission_repair_issue(self.hass, self._router.mac)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return _has_led_strip_support(self._router.lcd_config)
