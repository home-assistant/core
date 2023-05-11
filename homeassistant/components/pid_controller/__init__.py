"""The PID controller integration."""

from __future__ import annotations

from datetime import timedelta
import logging
import math
from typing import Any

from dvg_pid_controller import Constants as PID_CONST, PID_Controller as PID
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import service
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    ATTR_CYCLE_TIME,
    ATTR_LAST_CYCLE_START,
    ATTR_PID_ENABLE,
    ATTR_PID_ERROR,
    ATTR_PID_INPUT,
    ATTR_PID_KD,
    ATTR_PID_KI,
    ATTR_PID_KP,
    ATTR_PID_OUTPUT,
    ATTR_VALUE,
    CONF_CYCLE_TIME,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
    DOMAIN,
    SERVICE_ENABLE,
)

PLATFORMS = [Platform.NUMBER]
_LOGGER = logging.getLogger(__name__)


class PidBaseClass(Entity):
    """Base class for PID entities."""

    # pylint: disable=too-many-arguments
    def __init__(
        self, k_p=1, k_i=0.01, k_d=0, direction=PID_CONST.DIRECT, cycle_time="00:00:10"
    ):
        """Initialize PID base class."""
        self._pid = PID(k_p, k_i, k_d, direction)
        if isinstance(cycle_time, timedelta):
            self._attr_cycle_time = cycle_time
        else:
            self._attr_cycle_time = timedelta(**cycle_time)
        self._attr_last_cycle_start: str = None

    @property
    def pid_capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        attr = {}
        attr[ATTR_CYCLE_TIME] = self.cycle_time
        attr[ATTR_PID_KP] = str(self.k_p)
        attr[ATTR_PID_KI] = str(self.k_i)
        attr[ATTR_PID_KD] = str(self.k_d)
        attr[ATTR_PID_INPUT] = str(self.pid_input)
        attr[ATTR_PID_OUTPUT] = str(self.pid_output)
        attr[ATTR_PID_ERROR] = str(self.pid_error)
        attr[ATTR_LAST_CYCLE_START] = str((self.last_cycle_start,))
        attr[ATTR_PID_ENABLE] = str((self.enable_pid,))
        return attr

    async def _async_start_pid_cycle(self):
        """Start periodical cycle of PID controller.

        Call this when added to hass, and hass is fully started.
        """
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_pid_cycle, self._attr_cycle_time
            )
        )

    @property
    def cycle_time(self) -> str:
        """Return cycle time for PID controller."""
        return str(self._attr_cycle_time)

    @property
    def last_cycle_start(self) -> str:
        """Return last time the PID controller cycle started."""
        return str(self._attr_last_cycle_start)

    @property
    def k_p(self) -> float:
        """Get Kp of the PID regulator."""
        return self._pid.kp

    @property
    def k_i(self) -> float:
        """Ki of the PID regulator."""
        return self._pid.ki

    @property
    def k_d(self) -> float:
        """Kd of the PID regulator."""
        return self._pid.kd

    @property
    def enable_pid(self) -> bool:
        """PID controller enabled."""
        return self._pid.in_auto

    async def async_enable(self, value: bool):
        """Enable or disable PID regulator."""
        # Raise Not Yet implemented error; has to be implemented per controller
        # Use self._pid.set_mode (mode,
        #                input_state , output_state, optional:input2_state )
        raise NotImplementedError()

    def filter_nan(self, value: float):
        """Filter floats for NAN."""
        if math.isnan(value):
            return None
        return value

    @property
    def pid_input(self) -> float:
        """Calculate input value, differential or not."""
        return self.filter_nan(self._pid.last_input)

    @property
    def pid_output(self) -> float:
        """Return PID output value."""
        return self.filter_nan(self._pid.output)

    @property
    def pid_error(self) -> float:
        """Calculate the current error."""
        return self.filter_nan(self._pid.last_error)

    @callback
    async def _async_pid_cycle(self, args=None):
        """Cycle PID regulator.

        Will raise NotImplemented error; should be implemented per controller.
        Use self._pid.compute(input,optional:input2 ) and self._pid.output to
        calculate.
        Read the data from this controllers input and send the result to this
        controllers output.
        Don't forget to update last_cycle_start as below:
        self._attr_last_cycle_start = dt_util.utcnow().replace(microsecond=0)
        """
        raise NotImplementedError()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up slow PID Controller from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener.

    Called when the config entry options are changed.
    """
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


# pylint: disable=unused-argument
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services for PID entities."""

    @service.verify_domain_control(hass, DOMAIN)
    async def async_service_handle(service_call: ServiceCall) -> None:
        """Handle services.

        Dispatch the right service call to the right entity.
        """
        # Next code will do a service call to all entities in the
        # current domain that contain the entitiy_id form service_call data
        # hass.data will get all available platforms in this domain.
        await service.entity_service_call(
            hass,
            list(hass.data[DATA_ENTITY_PLATFORM][DOMAIN]),
            "async_" + service_call.service,
            service_call,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ENABLE,
        async_service_handle,
        cv.make_entity_service_schema({vol.Required(ATTR_VALUE): vol.Coerce(bool)}),
    )
    return True
