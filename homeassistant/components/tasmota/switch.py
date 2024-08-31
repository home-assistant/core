"""Support for Tasmota switches."""

from typing import Any

from hatasmota import relay as tasmota_relay
from hatasmota.entity import TasmotaEntity as HATasmotaEntity
from hatasmota.models import DiscoveryHashType

from homeassistant.components import switch
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate, TasmotaOnOffEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tasmota switch dynamically through discovery."""

    @callback
    def async_discover(
        tasmota_entity: HATasmotaEntity, discovery_hash: DiscoveryHashType
    ) -> None:
        """Discover and add a Tasmota switch."""
        async_add_entities(
            [
                TasmotaSwitch(
                    tasmota_entity=tasmota_entity, discovery_hash=discovery_hash
                )
            ]
        )

    hass.data[DATA_REMOVE_DISCOVER_COMPONENT.format(switch.DOMAIN)] = (
        async_dispatcher_connect(
            hass,
            TASMOTA_DISCOVERY_ENTITY_NEW.format(switch.DOMAIN),
            async_discover,
        )
    )


class TasmotaSwitch(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    TasmotaOnOffEntity,
    SwitchEntity,
):
    """Representation of a Tasmota switch."""

    _tasmota_entity: tasmota_relay.TasmotaRelay

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._tasmota_entity.set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._tasmota_entity.set_state(False)
