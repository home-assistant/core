"""Coordinator for lifx."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
from enum import IntEnum
from functools import partial
from math import floor, log10
from typing import Any, cast

from aiolifx.aiolifx import (
    Light,
    Message,
    MultiZoneDirection,
    MultiZoneEffectType,
    TileEffectType,
)
from aiolifx.connection import LIFXConnection
from aiolifx_themes.themes import ThemeLibrary, ThemePainter
from awesomeversion import AwesomeVersion

from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    _LOGGER,
    ATTR_REMAINING,
    DEFAULT_ATTEMPTS,
    DOMAIN,
    IDENTIFY_WAVEFORM,
    MAX_ATTEMPTS_PER_UPDATE_REQUEST_MESSAGE,
    MAX_UPDATE_TIME,
    MESSAGE_RETRIES,
    MESSAGE_TIMEOUT,
    OVERALL_TIMEOUT,
    TARGET_ANY,
    UNAVAILABLE_GRACE,
)
from .util import (
    async_execute_lifx,
    async_multi_execute_lifx_with_retries,
    get_real_mac_addr,
    infrared_brightness_option_to_value,
    infrared_brightness_value_to_option,
    lifx_features,
)

LIGHT_UPDATE_INTERVAL = 10
REQUEST_REFRESH_DELAY = 0.35
LIFX_IDENTIFY_DELAY = 3.0
ZONES_PER_COLOR_UPDATE_REQUEST = 8

RSSI_DBM_FW = AwesomeVersion("2.77")


class FirmwareEffect(IntEnum):
    """Enumeration of LIFX firmware effects."""

    OFF = 0
    MOVE = 1
    MORPH = 2
    FLAME = 3


class LIFXUpdateCoordinator(DataUpdateCoordinator[None]):
    """DataUpdateCoordinator to gather data for a specific lifx device."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: LIFXConnection,
        title: str,
    ) -> None:
        """Initialize DataUpdateCoordinator."""
        assert connection.device is not None
        self.connection = connection
        self.device: Light = connection.device
        self.lock = asyncio.Lock()
        self.active_effect = FirmwareEffect.OFF
        self._update_rssi: bool = False
        self._rssi: int = 0
        self.last_used_theme: str = ""

        super().__init__(
            hass,
            _LOGGER,
            name=f"{title} ({self.device.ip_addr})",
            update_interval=timedelta(seconds=LIGHT_UPDATE_INTERVAL),
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    @callback
    def async_setup(self) -> None:
        """Change timeouts."""
        self.device.timeout = MESSAGE_TIMEOUT
        self.device.retry_count = MESSAGE_RETRIES
        self.device.unregister_timeout = UNAVAILABLE_GRACE

    @property
    def rssi(self) -> int:
        """Return stored RSSI value."""
        return self._rssi

    @property
    def rssi_uom(self) -> str:
        """Return the RSSI unit of measurement."""
        if AwesomeVersion(self.device.host_firmware_version) <= RSSI_DBM_FW:
            return SIGNAL_STRENGTH_DECIBELS

        return SIGNAL_STRENGTH_DECIBELS_MILLIWATT

    @property
    def current_infrared_brightness(self) -> str | None:
        """Return the current infrared brightness as a string."""
        return infrared_brightness_value_to_option(self.device.infrared_brightness)

    @property
    def serial_number(self) -> str:
        """Return the internal mac address."""
        return cast(
            str, self.device.mac_addr
        )  # device.mac_addr is not the mac_address, its the serial number

    @property
    def mac_address(self) -> str:
        """Return the physical mac address."""
        return get_real_mac_addr(
            # device.mac_addr is not the mac_address, its the serial number
            self.device.mac_addr,
            self.device.host_firmware_version,
        )

    @property
    def label(self) -> str:
        """Return the label of the bulb."""
        return cast(str, self.device.label)

    async def diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the device."""
        features = lifx_features(self.device)
        device_data = {
            "firmware": self.device.host_firmware_version,
            "vendor": self.device.vendor,
            "product_id": self.device.product,
            "features": features,
            "hue": self.device.color[0],
            "saturation": self.device.color[1],
            "brightness": self.device.color[2],
            "kelvin": self.device.color[3],
            "power": self.device.power_level,
        }

        if features["multizone"] is True:
            zones = {"count": self.device.zones_count, "state": {}}
            for index, zone_color in enumerate(self.device.color_zones):
                zones["state"][index] = {
                    "hue": zone_color[0],
                    "saturation": zone_color[1],
                    "brightness": zone_color[2],
                    "kelvin": zone_color[3],
                }
            device_data["zones"] = zones

        if features["hev"] is True:
            device_data["hev"] = {
                "hev_cycle": self.device.hev_cycle,
                "hev_config": self.device.hev_cycle_configuration,
                "last_result": self.device.last_hev_cycle_result,
            }

        if features["infrared"] is True:
            device_data["infrared"] = {"brightness": self.device.infrared_brightness}

        return device_data

    def async_get_entity_id(self, platform: Platform, key: str) -> str | None:
        """Return the entity_id from the platform and key provided."""
        ent_reg = er.async_get(self.hass)
        return ent_reg.async_get_entity_id(
            platform, DOMAIN, f"{self.serial_number}_{key}"
        )

    async def _async_populate_device_info(self) -> None:
        """Populate device info."""
        methods: list[Callable] = []
        device = self.device
        if self.device.host_firmware_version is None:
            methods.append(device.get_hostfirmware)
        if self.device.product is None:
            methods.append(device.get_version)
        if self.device.group is None:
            methods.append(device.get_group)
        assert methods, "Device info already populated"
        await async_multi_execute_lifx_with_retries(
            methods, DEFAULT_ATTEMPTS, OVERALL_TIMEOUT
        )

    def get_number_of_zones(self) -> int:
        """Return the number of zones.

        If the number of zones is not yet populated, return 1 since
        the device will have a least one zone.
        """
        return len(self.device.color_zones) if self.device.color_zones else 1

    @callback
    def _async_build_color_zones_update_requests(self) -> list[Callable]:
        """Build a color zones update request."""
        device = self.device
        calls: list[Callable] = []
        for zone in range(
            0, self.get_number_of_zones(), ZONES_PER_COLOR_UPDATE_REQUEST
        ):

            def _wrap_get_color_zones(
                callb: Callable[[Message, dict[str, Any] | None], None],
                get_color_zones_args: dict[str, Any],
            ) -> None:
                """Capture the callback and make sure resp_set_multizonemultizone is called before."""

                def _wrapped_callback(
                    bulb: Light,
                    response: Message,
                    **kwargs: Any,
                ) -> None:
                    # We need to call resp_set_multizonemultizone to populate
                    # the color_zones attribute before calling the callback
                    device.resp_set_multizonemultizone(response)
                    # Now call the original callback
                    callb(bulb, response, **kwargs)

                device.get_color_zones(**get_color_zones_args, callb=_wrapped_callback)

            calls.append(
                partial(
                    _wrap_get_color_zones,
                    get_color_zones_args={
                        "start_index": zone,
                        "end_index": zone + ZONES_PER_COLOR_UPDATE_REQUEST - 1,
                    },
                )
            )

        return calls

    async def _async_update_data(self) -> None:
        """Fetch all device data from the api."""
        device = self.device
        if (
            device.host_firmware_version is None
            or device.product is None
            or device.group is None
        ):
            await self._async_populate_device_info()

        num_zones = self.get_number_of_zones()
        features = lifx_features(self.device)
        is_extended_multizone = features["extended_multizone"]
        is_legacy_multizone = not is_extended_multizone and features["multizone"]
        update_rssi = self._update_rssi
        methods: list[Callable] = [self.device.get_color]
        if update_rssi:
            methods.append(self.device.get_wifiinfo)
        if is_extended_multizone:
            methods.append(self.device.get_extended_color_zones)
        elif is_legacy_multizone:
            methods.extend(self._async_build_color_zones_update_requests())
        if is_extended_multizone or is_legacy_multizone:
            methods.append(self.device.get_multizone_effect)
        if features["hev"]:
            methods.append(self.device.get_hev_cycle)
        if features["infrared"]:
            methods.append(self.device.get_infrared)

        responses = await async_multi_execute_lifx_with_retries(
            methods, MAX_ATTEMPTS_PER_UPDATE_REQUEST_MESSAGE, MAX_UPDATE_TIME
        )
        # device.mac_addr is not the mac_address, its the serial number
        if device.mac_addr == TARGET_ANY:
            device.mac_addr = responses[0].target_addr

        if update_rssi:
            # We always send the rssi request second
            self._rssi = int(floor(10 * log10(responses[1].signal) + 0.5))

        if is_extended_multizone or is_legacy_multizone:
            self.active_effect = FirmwareEffect[self.device.effect.get("effect", "OFF")]
        if is_legacy_multizone and num_zones != self.get_number_of_zones():
            # The number of zones has changed so we need
            # to update the zones again. This happens rarely.
            await self.async_get_color_zones()

    async def async_get_color_zones(self) -> None:
        """Get updated color information for each zone."""
        await async_multi_execute_lifx_with_retries(
            self._async_build_color_zones_update_requests(),
            DEFAULT_ATTEMPTS,
            OVERALL_TIMEOUT,
        )

    async def async_get_extended_color_zones(self) -> None:
        """Get updated color information for all zones."""
        try:
            await async_execute_lifx(self.device.get_extended_color_zones)
        except TimeoutError as ex:
            raise HomeAssistantError(
                f"Timeout getting color zones from {self.name}"
            ) from ex

    async def async_set_waveform_optional(
        self, value: dict[str, Any], rapid: bool = False
    ) -> None:
        """Send a set_waveform_optional message to the device."""
        await async_execute_lifx(
            partial(self.device.set_waveform_optional, value=value, rapid=rapid)
        )

    async def async_get_color(self) -> None:
        """Send a get color message to the device."""
        await async_execute_lifx(self.device.get_color)

    async def async_set_power(self, state: bool, duration: int | None) -> None:
        """Send a set power message to the device."""
        await async_execute_lifx(
            partial(self.device.set_power, state, duration=duration)
        )

    async def async_set_color(
        self, hsbk: list[float | int | None], duration: int | None
    ) -> None:
        """Send a set color message to the device."""
        await async_execute_lifx(
            partial(self.device.set_color, hsbk, duration=duration)
        )

    async def async_set_color_zones(
        self,
        start_index: int,
        end_index: int,
        hsbk: list[float | int | None],
        duration: int | None,
        apply: int,
    ) -> None:
        """Send a set color zones message to the device."""
        await async_execute_lifx(
            partial(
                self.device.set_color_zones,
                start_index=start_index,
                end_index=end_index,
                color=hsbk,
                duration=duration,
                apply=apply,
            )
        )

    async def async_set_extended_color_zones(
        self,
        colors: list[tuple[int | float, int | float, int | float, int | float]],
        colors_count: int | None = None,
        duration: int = 0,
        apply: int = 1,
    ) -> None:
        """Send a single set extended color zones message to the device."""

        if colors_count is None:
            colors_count = len(colors)

        # pad the color list with blanks if necessary
        if len(colors) < 82:
            for _ in range(82 - len(colors)):
                colors.append((0, 0, 0, 0))

        await async_execute_lifx(
            partial(
                self.device.set_extended_color_zones,
                colors=colors,
                colors_count=colors_count,
                duration=duration,
                apply=apply,
            )
        )

    async def async_set_multizone_effect(
        self,
        effect: str,
        speed: float = 3.0,
        direction: str = "RIGHT",
        theme_name: str | None = None,
        power_on: bool = True,
    ) -> None:
        """Control the firmware-based Move effect on a multizone device."""
        if lifx_features(self.device)["multizone"] is True:
            if power_on and self.device.power_level == 0:
                await self.async_set_power(True, 0)

            if theme_name is not None:
                theme = ThemeLibrary().get_theme(theme_name)
                await ThemePainter(self.hass.loop).paint(
                    theme, [self.device], round(speed)
                )

            await async_execute_lifx(
                partial(
                    self.device.set_multizone_effect,
                    effect=MultiZoneEffectType[effect.upper()].value,
                    speed=speed,
                    direction=MultiZoneDirection[direction.upper()].value,
                )
            )
            self.active_effect = FirmwareEffect[effect.upper()]

    async def async_set_matrix_effect(
        self,
        effect: str,
        palette: list[tuple[int, int, int, int]] | None = None,
        speed: float = 3,
        power_on: bool = True,
    ) -> None:
        """Control the firmware-based effects on a matrix device."""
        if lifx_features(self.device)["matrix"] is True:
            if power_on and self.device.power_level == 0:
                await self.async_set_power(True, 0)

            if palette is None:
                palette = []

            await async_execute_lifx(
                partial(
                    self.device.set_tile_effect,
                    effect=TileEffectType[effect.upper()].value,
                    speed=speed,
                    palette=palette,
                )
            )
            self.active_effect = FirmwareEffect[effect.upper()]

    def async_get_active_effect(self) -> int:
        """Return the enum value of the currently active firmware effect."""
        return self.active_effect.value

    async def async_set_infrared_brightness(self, option: str) -> None:
        """Set infrared brightness."""
        infrared_brightness = infrared_brightness_option_to_value(option)
        await async_execute_lifx(partial(self.device.set_infrared, infrared_brightness))

    async def async_identify_bulb(self) -> None:
        """Identify the device by flashing it three times."""
        bulb: Light = self.device
        if bulb.power_level:
            # just flash the bulb for three seconds
            await self.async_set_waveform_optional(value=IDENTIFY_WAVEFORM)
            return
        # Turn the bulb on first, flash for 3 seconds, then turn off
        await self.async_set_power(state=True, duration=1)
        await self.async_set_waveform_optional(value=IDENTIFY_WAVEFORM)
        await asyncio.sleep(LIFX_IDENTIFY_DELAY)
        await self.async_set_power(state=False, duration=1)

    def async_enable_rssi_updates(self) -> Callable[[], None]:
        """Enable RSSI signal strength updates."""

        @callback
        def _async_disable_rssi_updates() -> None:
            """Disable RSSI updates when sensor removed."""
            self._update_rssi = False

        self._update_rssi = True
        return _async_disable_rssi_updates

    def async_get_hev_cycle_state(self) -> bool | None:
        """Return the current HEV cycle state."""
        if self.device.hev_cycle is None:
            return None
        return bool(self.device.hev_cycle.get(ATTR_REMAINING, 0) > 0)

    async def async_set_hev_cycle_state(self, enable: bool, duration: int = 0) -> None:
        """Start or stop an HEV cycle on a LIFX Clean bulb."""
        if lifx_features(self.device)["hev"]:
            await async_execute_lifx(
                partial(self.device.set_hev_cycle, enable=enable, duration=duration)
            )

    async def async_apply_theme(self, theme_name: str) -> None:
        """Apply the selected theme to the device."""
        self.last_used_theme = theme_name
        theme = ThemeLibrary().get_theme(theme_name)
        await ThemePainter(self.hass.loop).paint(theme, [self.device])
