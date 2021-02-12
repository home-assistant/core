"""Representation of Z-Wave switches."""

import logging
from typing import Any, Callable, List, Optional

from zwave_js_server.client import Client as ZwaveClient

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

LOGGER = logging.getLogger(__name__)


BARRIER_EVENT_SIGNALING_OFF = 0
BARRIER_EVENT_SIGNALING_ON = 255


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave sensor from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_switch(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Switch."""
        entities: List[ZWaveBaseEntity] = []
        if info.platform_hint == "barrier_event_signaling_state":
            entities.append(
                ZWaveBarrierEventSignalingSwitch(config_entry, client, info)
            )
        else:
            entities.append(ZWaveSwitch(config_entry, client, info))

        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{SWITCH_DOMAIN}",
            async_add_switch,
        )
    )


class ZWaveSwitch(ZWaveBaseEntity, SwitchEntity):
    """Representation of a Z-Wave switch."""

    @property
    def is_on(self) -> Optional[bool]:  # type: ignore
        """Return a boolean for the state of the switch."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return bool(self.info.primary_value.value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        target_value = self.get_zwave_value("targetValue")
        if target_value is not None:
            await self.info.node.async_set_value(target_value, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        target_value = self.get_zwave_value("targetValue")
        if target_value is not None:
            await self.info.node.async_set_value(target_value, False)


class ZWaveBarrierEventSignalingSwitch(ZWaveBaseEntity, SwitchEntity):
    """This switch is used to turn on or off a barrier device's event signaling subsystem."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveBarrierEventSignalingSwitch entity."""
        super().__init__(config_entry, client, info)
        self._name = self.generate_name(include_value_name=True)
        self._state: Optional[bool] = None

        self._update_state()

    @callback
    def on_value_update(self) -> None:
        """Call when a watched value is added or updated."""
        self._update_state()

    @property
    def name(self) -> str:
        """Return default name from device name and value name combination."""
        return self._name

    @property
    def is_on(self) -> Optional[bool]:  # type: ignore
        """Return a boolean for the state of the switch."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.info.node.async_set_value(
            self.info.primary_value, BARRIER_EVENT_SIGNALING_ON
        )
        # this value is not refreshed, so assume success
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.info.node.async_set_value(
            self.info.primary_value, BARRIER_EVENT_SIGNALING_OFF
        )
        # this value is not refreshed, so assume success
        self._state = False
        self.async_write_ha_state()

    @callback
    def _update_state(self) -> None:
        self._state = None
        if self.info.primary_value.value is not None:
            self._state = self.info.primary_value.value == BARRIER_EVENT_SIGNALING_ON
