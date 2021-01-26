"""Support for Genius Hub switch/outlet devices."""
from datetime import timedelta
from typing import Optional

import voluptuous as vol

from homeassistant.components.switch import DEVICE_CLASS_OUTLET, SwitchEntity
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import (
    ATTR_DURATION,
    DOMAIN,
    SET_SWITCH_OVERRIDE_SCHEMA,
    SVC_SET_SWITCH_OVERRIDE,
    GeniusZone,
)

GH_ON_OFF_ZONE = "on / off"


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
) -> None:
    """Set up the Genius Hub switch entities."""
    if discovery_info is None:
        return

    broker = hass.data[DOMAIN]["broker"]

    async_add_entities(
        [
            GeniusSwitch(broker, z)
            for z in broker.client.zone_objs
            if z.data["type"] == GH_ON_OFF_ZONE
        ]
    )

    async def set_switch_override(call) -> None:
        """Set the system mode."""
        entity_id = call.data[ATTR_ENTITY_ID]

        registry = await hass.helpers.entity_registry.async_get_registry()
        registry_entry = registry.async_get(entity_id)

        if registry_entry is None or registry_entry.platform != DOMAIN:
            raise ValueError(f"'{entity_id}' is not a known {DOMAIN} entity")

        if registry_entry.domain != "switch":
            raise ValueError(f"'{entity_id}' is not an {DOMAIN} zone")

        payload = {
            "unique_id": registry_entry.unique_id,
            "service": call.service,
            "data": call.data,
        }
        async_dispatcher_send(hass, DOMAIN, payload)

    hass.services.async_register(
        DOMAIN,
        SVC_SET_SWITCH_OVERRIDE,
        set_switch_override,
        schema=SET_SWITCH_OVERRIDE_SCHEMA,
    )


class GeniusSwitch(GeniusZone, SwitchEntity):
    """Representation of a Genius Hub switch."""

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_OUTLET

    async def _refresh(self, payload: Optional[dict] = None) -> None:
        """Process any signals."""
        if payload is None:
            self.async_schedule_update_ha_state(force_refresh=True)
            return

        if payload["unique_id"] != self._unique_id:
            return

        if payload["service"] == SVC_SET_SWITCH_OVERRIDE:
            duration = payload["data"].get(ATTR_DURATION, timedelta(hours=1))

            await self._zone.set_override(1, int(duration.total_seconds()))
            return

        raise TypeError(f"'{self.entity_id}' is not a geniushub switch")

    @property
    def is_on(self) -> bool:
        """Return the current state of the on/off zone.

        The zone is considered 'on' if & only if it is override/on (e.g. timer/on is 'off').
        """
        return self._zone.data["mode"] == "override" and self._zone.data["setpoint"]

    async def async_turn_off(self, **kwargs) -> None:
        """Send the zone to Timer mode.

        The zone is deemed 'off' in this mode, although the plugs may actually be on.
        """
        await self._zone.set_mode("timer")

    async def async_turn_on(self, **kwargs) -> None:
        """Set the zone to override/on ({'setpoint': true}) for x seconds."""
        await self._zone.set_override(1, kwargs.get(ATTR_DURATION, 3600))
