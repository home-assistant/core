"""Coordinator for LIFX."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import cast, override

from lifx import (
    STATE_REFRESH_DEBOUNCE_MS,
    CeilingLightState,
    Colors,
    Device,
    HevLight,
    HevLightState,
    InfraredLight,
    InfraredLightState,
    LifxError,
    Light,
    LightState,
    LightWaveform,
    MatrixLight,
    MatrixLightState,
    MultiZoneLight,
    MultiZoneLightState,
    ThemeLibrary,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, INFRARED_LEVELS, LIFX_IDENTIFY_DELAY, LOGGER
from .util import device_error

type LIFXState = (
    LightState
    | MultiZoneLightState
    | MatrixLightState
    | CeilingLightState
    | HevLightState
    | InfraredLightState
)

type LIFXConfigEntry = ConfigEntry[LIFXUpdateCoordinator]


class LIFXUpdateCoordinator(DataUpdateCoordinator[LIFXState]):
    """Gather typed state for one persistent LIFX device."""

    def __init__(
        self, hass: HomeAssistant, entry: LIFXConfigEntry, device: Device
    ) -> None:
        """Initialize the coordinator."""
        self.device = device
        self.last_used_theme: str | None = None
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{entry.title} ({device.ip})",
            update_interval=timedelta(seconds=10),
            # The library already holds a write back until the device settles, so
            # only its own debounce window has to be waited out, not the ten
            # second default that would leave the UI stale after a command
            request_refresh_debouncer=Debouncer(
                hass,
                LOGGER,
                cooldown=STATE_REFRESH_DEBOUNCE_MS / 1000,
                immediate=True,
            ),
        )

    @override
    async def _async_update_data(self) -> LIFXState:
        """Refresh all state through the public library boundary."""
        try:
            await self.device.refresh_state()
        except LifxError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        state = self.device.state
        assert state is not None
        return cast(LIFXState, state)

    @property
    def serial_number(self) -> str:
        """Return the raw LIFX serial that identifies the device."""
        return self.data.serial

    @property
    def infrared_brightness(self) -> float:
        """Return the infrared brightness as a percentage."""
        assert isinstance(self.data, InfraredLightState)
        return round(self.data.infrared * 100)

    @property
    def current_infrared_brightness(self) -> str | None:
        """Return the current infrared brightness option, if it is one of them."""
        assert isinstance(self.data, InfraredLightState)
        # Firmware answers with a uint16 step, which can sit either side of ours
        infrared = round(self.data.infrared * 65535)
        return next(
            (
                option
                for option, level in INFRARED_LEVELS.items()
                if abs(round(level * 65535) - infrared) <= 1
            ),
            None,
        )

    @property
    def rssi(self) -> int | None:
        """Return the library-calculated signal strength."""
        return self.data.wifi_info.rssi

    @property
    def rssi_uom(self) -> str | None:
        """Return the library-classified signal-strength unit.

        The library resolves the unit from the firmware version, so it is on
        the state from the first refresh even while the signal itself is not
        being read: a sensor registered without a unit and given one later
        breaks its long term statistics.
        """
        return self.data.wifi_info.rssi_unit

    def async_get_entity_id(self, platform: Platform, key: str) -> str | None:
        """Return the entity ID for a platform and key."""
        return er.async_get(self.hass).async_get_entity_id(
            platform, DOMAIN, f"{self.serial_number}_{key}"
        )

    async def async_restart(self) -> None:
        """Restart the device."""
        try:
            await self.device.set_reboot()
        except LifxError as err:
            raise device_error(err) from err

    async def _async_flash_bulb(self) -> None:
        """Flash the device to full-brightness neutral white three times."""
        assert isinstance(self.device, Light)
        await self.device.set_waveform_optional(
            Colors.WHITE_NEUTRAL,
            period=1.0,
            cycles=3,
            waveform=LightWaveform.SINE,
        )

    async def async_identify_bulb(self) -> None:
        """Identify the device by flashing it three times."""
        assert isinstance(self.device, Light)
        try:
            if self.data.power != 0:
                await self._async_flash_bulb()
                return
            # Turn the bulb on first, flash for three seconds, then turn off
            await self.device.set_power(True, duration=1.0)
            await self._async_flash_bulb()
            await asyncio.sleep(LIFX_IDENTIFY_DELAY)
            await self.device.set_power(False, duration=1.0)
        except LifxError as err:
            raise device_error(err) from err

    def async_enable_rssi_updates(self) -> Callable[[], None]:
        """Read the signal strength while the RSSI sensor is added.

        The signal costs an extra request per refresh, so it is left out while
        nothing is reporting it. Its unit comes with the state either way.
        """

        @callback
        def _async_disable_rssi_updates() -> None:
            self.device.fetch_wifi_info = False

        self.device.fetch_wifi_info = True
        return _async_disable_rssi_updates

    async def async_set_infrared_brightness(self, brightness: float) -> None:
        """Set infrared brightness from a percentage."""
        assert isinstance(self.device, InfraredLight)
        try:
            await self.device.set_infrared(brightness / 100)
        except LifxError as err:
            raise device_error(err) from err

    async def async_set_hev_cycle_state(self, enable: bool, duration: int = 0) -> None:
        """Start or stop an HEV cycle."""
        assert isinstance(self.device, HevLight)
        try:
            await self.device.set_hev_cycle(enable, duration)
        except LifxError as err:
            raise device_error(err) from err

    async def async_apply_theme(self, theme_name: str) -> None:
        """Apply a built-in theme to a zone-based device."""
        assert isinstance(self.device, (MultiZoneLight, MatrixLight))
        try:
            await self.device.apply_theme(ThemeLibrary.get(theme_name))
        except LifxError as err:
            raise device_error(err) from err
        self.last_used_theme = theme_name
