"""Platform to locally control Tuya-based fan devices."""
import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.fan import (
    DOMAIN,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
    FanEntity,
)

from .common import LocalTuyaEntity, async_setup_entry
from .const import (
    CONF_FAN_OSCILLATING_CONTROL,
    CONF_FAN_SPEED_CONTROL,
    CONF_FAN_SPEED_HIGH,
    CONF_FAN_SPEED_LOW,
    CONF_FAN_SPEED_MEDIUM,
)

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_FAN_SPEED_CONTROL): vol.In(dps),
        vol.Optional(CONF_FAN_OSCILLATING_CONTROL): vol.In(dps),
        vol.Optional(CONF_FAN_SPEED_LOW, default=SPEED_LOW): vol.In(
            [SPEED_LOW, "1", "2", "small"]
        ),
        vol.Optional(CONF_FAN_SPEED_MEDIUM, default=SPEED_MEDIUM): vol.In(
            [SPEED_MEDIUM, "mid", "2", "3"]
        ),
        vol.Optional(CONF_FAN_SPEED_HIGH, default=SPEED_HIGH): vol.In(
            [SPEED_HIGH, "auto", "3", "4", "large", "big"]
        ),
    }


class LocaltuyaFan(LocalTuyaEntity, FanEntity):
    """Representation of a Tuya fan."""

    def __init__(
        self,
        device,
        config_entry,
        fanid,
        **kwargs,
    ):
        """Initialize the entity."""
        super().__init__(device, config_entry, fanid, _LOGGER, **kwargs)
        self._is_on = False
        self._speed = None
        self._oscillating = None

    @property
    def oscillating(self):
        """Return current oscillating status."""
        return self._oscillating

    @property
    def is_on(self):
        """Check if Tuya fan is on."""
        return self._is_on

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return self._speed

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the entity."""
        await self._device.set_dp(True, self._dp_id)
        if speed is not None:
            await self.async_set_speed(speed)
        else:
            self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity."""
        await self._device.set_dp(False, self._dp_id)
        self.schedule_update_ha_state()

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        mapping = {
            SPEED_LOW: self._config.get(CONF_FAN_SPEED_LOW),
            SPEED_MEDIUM: self._config.get(CONF_FAN_SPEED_MEDIUM),
            SPEED_HIGH: self._config.get(CONF_FAN_SPEED_HIGH),
        }

        if speed == SPEED_OFF:
            await self._device.set_dp(False, self._dp_id)
        else:
            await self._device.set_dp(
                mapping.get(speed), self._config.get(CONF_FAN_SPEED_CONTROL)
            )

        self.schedule_update_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        await self._device.set_dp(
            oscillating, self._config.get(CONF_FAN_OSCILLATING_CONTROL)
        )
        self.schedule_update_ha_state()

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        supports = 0

        if self.has_config(CONF_FAN_OSCILLATING_CONTROL):
            supports |= SUPPORT_OSCILLATE
        if self.has_config(CONF_FAN_SPEED_CONTROL):
            supports |= SUPPORT_SET_SPEED

        return supports

    def status_updated(self):
        """Get state of Tuya fan."""
        mappings = {
            self._config.get(CONF_FAN_SPEED_LOW): SPEED_LOW,
            self._config.get(CONF_FAN_SPEED_MEDIUM): SPEED_MEDIUM,
            self._config.get(CONF_FAN_SPEED_HIGH): SPEED_HIGH,
        }

        self._is_on = self.dps(self._dp_id)

        if self.has_config(CONF_FAN_SPEED_CONTROL):
            self._speed = mappings.get(self.dps_conf(CONF_FAN_SPEED_CONTROL))
            if self.speed is None:
                self.warning(
                    "%s/%s: Ignoring unknown fan controller state: %s",
                    self.name,
                    self.entity_id,
                    self.dps_conf(CONF_FAN_SPEED_CONTROL),
                )
                self._speed = None

        if self.has_config(CONF_FAN_OSCILLATING_CONTROL):
            self._oscillating = self.dps_conf(CONF_FAN_OSCILLATING_CONTROL)


async_setup_entry = partial(async_setup_entry, DOMAIN, LocaltuyaFan, flow_schema)
