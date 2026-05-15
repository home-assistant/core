from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, FLAME_MIN, FLAME_MAX
from .mertik import Mertik

_LOGGER = logging.getLogger(__name__)
OPTIMISTIC_ON_SECONDS = 20
OPTIMISTIC_OFF_SECONDS = 20


class MertikDataCoordinator(DataUpdateCoordinator[None]):
    def __init__(
        self, hass: HomeAssistant, mertik: Mertik, entry: ConfigEntry | None = None
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Mertik",
            update_interval=timedelta(seconds=10),
        )
        self.mertik = mertik
        self._optimistic_on_until: datetime | None = None
        self._optimistic_off_until: datetime | None = None
        self._prev_is_on: bool = False
        self.fire_just_turned_off: bool = (
            False  # set True for one cycle when fire turns off
        )
        self._in_standby: bool = False  # True when thermostatic standby is active
        self._pending_mode: str | None = None  # mode to apply once ignition completes
        self._pending_mode_since: datetime | None = (
            None  # when _pending_mode was set (for timeout)
        )
        self._heating_mode: str | None = (
            None  # current mode set by the Heating Mode select entity
        )
        self._was_igniting: bool = False  # tracks igniting falling edge
        self._flame_on_since: datetime | None = (
            None  # timestamp when flame first lit after ignite
        )
        self._settle_seconds: int = 35  # seconds to wait after flame_on before aux_off
        self._ignition_timeout_seconds: int = (
            120  # abandon pending mode after this many seconds
        )
        self._is_light_on: bool = False
        self._light_brightness: int = 0

    # ---- On/off state ----------------------------------------------------
    # Use flame_on (flame byte > threshold) as the primary "is fire running"
    # indicator. on_flag ("FF") is only set when ignite_fireplace() is used,
    # not when set_flame_height() starts the fire.

    @property
    def is_on(self) -> bool:
        """Fire is running -- based on flame byte, standby state, or optimistic timer.

        _in_standby (pilot lit, thermostatic armed) takes priority over the
        optimistic-off timer so the Fireplace switch stays on while in standby.
        """
        if self._in_standby:
            return True
        now = dt_util.utcnow()
        if self._optimistic_off_until and now < self._optimistic_off_until:
            return False
        if self.mertik.is_flame_on or self.mertik.is_igniting:
            return True
        if self._optimistic_on_until and now < self._optimistic_on_until:
            return True
        return False

    def mark_optimistic_on(self) -> None:
        self._optimistic_off_until = None
        self._optimistic_on_until = dt_util.utcnow() + timedelta(
            seconds=OPTIMISTIC_ON_SECONDS
        )

    def mark_optimistic_off(self) -> None:
        self._optimistic_on_until = None
        self._optimistic_off_until = dt_util.utcnow() + timedelta(
            seconds=OPTIMISTIC_OFF_SECONDS
        )

    @property
    def heating_mode(self) -> str | None:
        return self._heating_mode

    def set_heating_mode(self, mode: str) -> None:
        self._heating_mode = mode

    def ignite_fireplace(self) -> None:
        self.mertik.ignite_fireplace()

    def guard_flame_off(self) -> None:
        self._optimistic_on_until = None
        self._optimistic_off_until = None
        self.mertik.guard_flame_off()
        self._in_standby = False
        self._pending_mode = None  # discard any in-flight ignition/mode sequence
        self._pending_mode_since = None
        self._flame_on_since = None
        # Signal light entity that fire turned off (device kills light too)
        self.fire_just_turned_off = True
        self._prev_is_on = False

    def standby(self) -> None:
        """Pilot flame only -- main burners off but ignition source stays lit.
        Used by thermostatic Off so re-ignition is fast when heat is needed.
        Does NOT set fire_just_turned_off because the device keeps the light
        on in standby mode (only guard_flame_off kills the light).
        """
        # CMD_STANDBY re-lights the pilot even from a fully-off state, so only
        # send it when the fire is currently on. This prevents two problems:
        # 1. User selects "Standby" from the Heating Mode select with fire off.
        # 2. A stale _do_standby task from a previous thermostatic poll runs
        #    after guard_flame_off + mark_optimistic_off (is_on = False during
        #    the optimistic-off window).
        if not self.is_on:
            _LOGGER.debug("standby() skipped: fire is not on")
            return
        self._optimistic_on_until = None
        self._optimistic_off_until = None
        self._in_standby = True
        self.mertik.standBy()

    def arm_thermostatic(self) -> None:
        """Arm thermostatic mode from the Fireplace switch.

        Sends CMD_STANDBY to light the pilot flame, then the climate entity's
        poll loop will ignite the main burner or leave the pilot running
        depending on whether the room needs heat.

        Unlike standby(), this works from a fully-off state -- it is only
        called when the user explicitly presses the Fireplace switch On while
        thermostatic mode is selected.  standby() keeps its is_on guard to
        prevent the Heating Mode select and the thermostatic loop from
        re-lighting the pilot after the user has turned the fire off.
        """
        self._optimistic_on_until = None
        self._optimistic_off_until = None
        self._pending_mode = None
        self._pending_mode_since = None
        self._in_standby = True
        self.mertik.standBy()

    @property
    def is_aux_on(self) -> bool:
        return self.mertik.is_aux_on  # already gated on flame_on in mertik.py

    def aux_on(self) -> None:
        self.mertik.aux_on()

    def aux_off(self) -> None:
        self.mertik.aux_off()

    def get_flame_height(self) -> int:
        return self.mertik.get_flame_height()

    def set_flame_height(self, flame_height: int) -> None:
        self.mertik.set_flame_height(flame_height)

    @property
    def fault_code(self) -> int:
        return self.mertik.fault_code

    @property
    def is_handset_connected(self) -> bool:
        return self.mertik.is_handset_connected

    @property
    def ambient_temperature(self) -> float:
        return self.mertik.ambient_temperature

    @property
    def is_light_on(self) -> bool:
        return self._is_light_on

    def light_on(self) -> None:
        self._is_light_on = True
        self.mertik.light_on()

    def light_off(self) -> None:
        self._is_light_on = False
        self.mertik.light_off()

    def set_light_brightness(self, brightness: int) -> None:
        self._light_brightness = brightness
        self.mertik.set_light_brightness(brightness)

    @property
    def light_brightness(self) -> int:
        return self._light_brightness

    def apply_heating_mode(self, mode: str | None) -> None:
        """Apply a named heating mode to the physical fireplace.

        Standby is handled first -- it must never trigger ignition regardless
        of the current fire state.

        For heat modes, two paths:
        1. Fire not physically on (is_flame_on=False, is_igniting=False):
           a. User switched off (is_on=False, _in_standby=False): block, do nothing.
           b. Optimistically on (user pressed On) or in thermostatic standby:
              ignite and defer via _pending_mode. In standby the pilot may have
              gone out, so always ignite to be safe -- sending flame-height commands
              to an extinguished device clears _in_standby and makes is_on go False
              (the 'turns itself off' symptom).
        2. Fire physically on (is_flame_on or is_igniting): apply mode directly.
        """
        from .const import MODE_STANDBY, MODE_FULL, MODE_MEDIUM, MODE_LOW

        # Standby never ignites -- handle it unconditionally before ignition logic.
        if mode == MODE_STANDBY:
            self._pending_mode = None
            self._pending_mode_since = None
            self.standby()
            return

        physically_on = self.mertik.is_flame_on or self.mertik.is_igniting

        if not physically_on:
            # Block if user explicitly switched off -- not optimistically on or standby.
            if not self.is_on and not self._in_standby:
                _LOGGER.debug(
                    "apply_heating_mode: fire is off by user, not igniting for %s", mode
                )
                return
            # Either optimistically on (user pressed On) or in thermostatic standby.
            # mark_optimistic_on clears any pending opt-off timer and bridges the gap
            # between ignition and the next poll confirming is_flame_on=True.
            self._pending_mode = mode
            self._pending_mode_since = dt_util.utcnow()
            self._in_standby = False
            self.mark_optimistic_on()
            self.mertik.ignite_fireplace()
            return

        # Fire is physically on (flame_on or igniting): apply mode directly.
        self._in_standby = False
        self._pending_mode = None
        self._pending_mode_since = None
        if mode == MODE_FULL:
            self.mertik.set_flame_height(FLAME_MAX)
            self.mertik.aux_on()
        elif mode == MODE_MEDIUM:
            self.mertik.aux_off()
            self.mertik.set_flame_height(FLAME_MAX)
        elif mode == MODE_LOW:
            self.mertik.aux_off()
            self.mertik.set_flame_height(FLAME_MIN)

    def check_pending_mode(self) -> bool:
        """Called by the thermostatic loop each poll cycle.

        Returns True if a pending mode was applied (so the caller knows
        to skip its normal mode calculation this cycle).

        After the burner lights, we wait _settle_seconds before sending
        aux_off / set_flame_height. The device firmware ignores these
        commands if sent too soon after ignition (ACK is received but
        the physical state does not change). 35 seconds is conservative
        but reliable based on observed device behaviour.
        """
        if not self._pending_mode:
            return False
        # Abandon pending mode if ignition has taken too long (e.g. failed ignition
        # leaves is_igniting stuck True indefinitely via flame_byte bit 4).
        if self._pending_mode_since is not None:
            elapsed = (dt_util.utcnow() - self._pending_mode_since).total_seconds()
            if elapsed > self._ignition_timeout_seconds:
                _LOGGER.warning(
                    "Ignition timeout after %.0fs — abandoning pending mode %s",
                    elapsed,
                    self._pending_mode,
                )
                self._pending_mode = None
                self._pending_mode_since = None
                self._flame_on_since = None
                return False
        # Still igniting -- wait
        if self.mertik.is_igniting:
            _LOGGER.debug(
                "Waiting for ignition to complete before applying %s",
                self._pending_mode,
            )
            self._flame_on_since = None
            return True
        # Igniting bit just dropped False -- flame_on may lag by one poll cycle.
        if not self.mertik.is_flame_on:
            _LOGGER.debug("Igniting cleared but flame_on not yet set -- waiting")
            return True
        # Burner is lit -- start the settle timer if not already started
        if self._flame_on_since is None:
            self._flame_on_since = dt_util.utcnow()
            _LOGGER.info(
                "Burner lit, waiting %ds before applying %s",
                self._settle_seconds,
                self._pending_mode,
            )
            return True
        # Check if enough time has passed since the burner lit
        elapsed = (dt_util.utcnow() - self._flame_on_since).total_seconds()
        if elapsed < self._settle_seconds:
            _LOGGER.debug(
                "Settling: %.0fs / %ds before applying %s",
                elapsed,
                self._settle_seconds,
                self._pending_mode,
            )
            return True
        # Settle period complete -- apply the deferred mode
        _LOGGER.info(
            "Settled (%.0fs), applying deferred mode %s", elapsed, self._pending_mode
        )
        mode = self._pending_mode
        self._pending_mode = None
        self._pending_mode_since = None
        self._flame_on_since = None
        self.apply_heating_mode(mode)
        return True

    async def _async_update_data(self) -> None:
        try:
            await self.hass.async_add_executor_job(self.mertik.refresh_status)
            ir.async_delete_issue(self.hass, DOMAIN, "cannot_connect")
            # Detect when fire turns off so light entity can reset its state.
            # The device physically turns the light off when fire is extinguished.
            current_on = self.is_on
            self.fire_just_turned_off = self._prev_is_on and not current_on
            self._prev_is_on = current_on
        except Exception as err:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "cannot_connect",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="cannot_connect",
                translation_placeholders={"host": self.mertik.ip},
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
