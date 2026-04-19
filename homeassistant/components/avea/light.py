"""Light platform for Avea."""

from __future__ import annotations

from contextlib import suppress
import logging
import threading
from typing import Any

import avea
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from homeassistant.components import bluetooth
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import color as color_util

from . import AveaConfigEntry
from .const import DOMAIN, INTEGRATION_TITLE, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)
UPDATE_EXCEPTIONS = (BleakError, OSError, RuntimeError)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AveaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Avea light platform."""
    async_add_entities([AveaLight(hass, entry)], update_before_add=True)


def _discover_bulbs_for_import() -> list[dict[str, str]]:
    """Discover and validate Avea bulbs for YAML import."""
    discovered_bulbs: list[dict[str, str]] = []

    for bulb in avea.discover_avea_bulbs():
        address = getattr(bulb.addr, "address", bulb.addr)
        try:
            name = bulb.get_name()
            bulb.get_brightness()
        except UPDATE_EXCEPTIONS as err:
            _LOGGER.warning(
                "Skipping Avea bulb %s during YAML import due to read failure: %s",
                address,
                err,
            )
            continue
        finally:
            with suppress(*UPDATE_EXCEPTIONS):
                bulb.close()

        discovered_bulbs.append(
            {
                CONF_ADDRESS: address,
                CONF_NAME: name or getattr(bulb, "name", None) or address,
            }
        )

    return discovered_bulbs


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the Avea YAML platform into config entries."""
    try:
        bulbs = await hass.async_add_executor_job(_discover_bulbs_for_import)
    except UPDATE_EXCEPTIONS as err:
        raise PlatformNotReady("Could not discover Avea bulbs for YAML import") from err

    if not bulbs:
        raise PlatformNotReady("Could not discover any Avea bulbs for YAML import")

    for bulb in bulbs:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=bulb,
        )

        if result.get("type") is FlowResultType.ABORT:
            if result.get("reason") == "already_configured":
                continue
            raise PlatformNotReady(
                f"Could not import Avea bulb {bulb[CONF_ADDRESS]}: {result.get('reason')}"
            )

        if result.get("type") is not FlowResultType.CREATE_ENTRY:
            raise PlatformNotReady(
                f"Unexpected result while importing Avea bulb {bulb[CONF_ADDRESS]}"
            )

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2026.10.0",
        is_fixable=False,
        is_persistent=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


class AveaLight(LightEntity):
    """Representation of an Avea."""

    _attr_color_mode = None
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.HS}

    def __init__(self, hass: HomeAssistant, entry: AveaConfigEntry) -> None:
        """Initialize an AveaLight."""
        self.hass = hass
        self._light = entry.runtime_data
        self._address: str = entry.data[CONF_ADDRESS]
        self._operation_lock = threading.Lock()
        self._attr_unique_id = self._address
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            connections={(CONNECTION_BLUETOOTH, self._address)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=entry.title,
        )

    def _sync_update(
        self, ble_device: BLEDevice | None
    ) -> tuple[int, tuple[int, int, int]]:
        """Fetch the latest state from the device."""
        with self._operation_lock:
            if ble_device is not None:
                self._light.addr = ble_device

            if not self._light.connect():
                raise ConnectionError(
                    f"Could not connect to Avea device {self._address}"
                )

            try:
                brightness = self._light.get_brightness()
                rgb = self._light.get_rgb()
            finally:
                self._light.close()

        return brightness, rgb

    def _sync_turn_on(
        self,
        ble_device: BLEDevice | None,
        brightness: int | None,
        hs_color: tuple[float, float] | None,
        was_on: bool,
    ) -> None:
        """Instruct the light to turn on."""
        with self._operation_lock:
            if ble_device is not None:
                self._light.addr = ble_device

            if not self._light.connect():
                raise ConnectionError(
                    f"Could not connect to Avea device {self._address}"
                )

            try:
                if brightness is None and hs_color is None:
                    self._light.set_brightness(4095)
                    return

                if brightness is not None:
                    self._light.set_brightness(round((brightness / 255) * 4095))

                if hs_color is not None:
                    rgb = color_util.color_hs_to_RGB(*hs_color)
                    self._light.set_rgb(rgb[0], rgb[1], rgb[2])
                    if brightness is None and not was_on:
                        self._light.set_brightness(4095)
            finally:
                self._light.close()

    def _sync_turn_off(self, ble_device: BLEDevice | None) -> None:
        """Instruct the light to turn off."""
        with self._operation_lock:
            if ble_device is not None:
                self._light.addr = ble_device

            if not self._light.connect():
                raise ConnectionError(
                    f"Could not connect to Avea device {self._address}"
                )

            try:
                self._light.set_brightness(0)
            finally:
                self._light.close()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        brightness: int | None = kwargs.get(ATTR_BRIGHTNESS)
        hs_color: tuple[float, float] | None = kwargs.get(ATTR_HS_COLOR)
        was_on = self._attr_is_on is True
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )

        await self.hass.async_add_executor_job(
            self._sync_turn_on, ble_device, brightness, hs_color, was_on
        )
        self._attr_available = True

        if not kwargs:
            self._attr_brightness = 255
            self._attr_is_on = True
        else:
            if hs_color is not None:
                self._attr_hs_color = hs_color

            if brightness is not None:
                self._attr_brightness = brightness
                self._attr_is_on = brightness > 0
            elif hs_color is not None and not was_on:
                self._attr_brightness = 255
                self._attr_is_on = True

        self._attr_color_mode = ColorMode.HS if self._attr_is_on else None

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        await self.hass.async_add_executor_job(self._sync_turn_off, ble_device)
        self._attr_available = True
        self._attr_is_on = False
        self._attr_brightness = 0
        self._attr_color_mode = None

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        try:
            brightness, rgb = await self.hass.async_add_executor_job(
                self._sync_update, ble_device
            )
        except ConnectionError:
            self._attr_available = False
            return
        except UPDATE_EXCEPTIONS:
            _LOGGER.warning(
                "Unexpected error while updating Avea device %s",
                self._address,
                exc_info=True,
            )
            self._attr_available = False
            return

        if brightness is None:
            _LOGGER.warning(
                "Avea device %s returned invalid brightness data during update",
                self._address,
            )
            self._attr_available = False
            return

        try:
            hs_color = color_util.color_RGB_to_hs(*rgb)
        except TypeError, ValueError:
            _LOGGER.warning(
                "Avea device %s returned invalid color data during update",
                self._address,
                exc_info=True,
            )
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_is_on = brightness != 0
        self._attr_brightness = round(255 * (brightness / 4095))
        self._attr_color_mode = ColorMode.HS if self._attr_is_on else None
        self._attr_hs_color = hs_color
