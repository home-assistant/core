"""Support for Netatmo/BTicino/Legrande switches."""

from __future__ import annotations

import logging
from typing import Any

from pyatmo import DeviceType, modules as NaModules
from pyatmo.person import Person

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_URL_CONTROL,
    CONF_URL_SECURITY,
    DOMAIN,
    NETATMO_CREATE_PERSON_SWITCHES,
    NETATMO_CREATE_SWITCH,
    PERSONS_DEVICE_IDENTIFIER_SUFFIX,
    PERSONS_DEVICE_NAME_SUFFIX,
)
from .data_handler import HOME, SIGNAL_NAME, NetatmoDevice, NetatmoPerson
from .entity import NetatmoDeviceEntity, NetatmoModuleEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Netatmo switch platform."""

    @callback
    def _create_entity(netatmo_device: NetatmoDevice) -> None:
        entity = NetatmoSwitch(netatmo_device)
        _LOGGER.debug("Adding switch %s", entity)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_SWITCH, _create_entity)
    )

    @callback
    def _create_person_switch_entities(persons: list[NetatmoPerson]) -> None:
        entities = [NetatmoPersonHomeSwitch(person) for person in persons]
        _LOGGER.debug("Adding person home switches %s", entities)
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_PERSON_SWITCHES, _create_person_switch_entities
        )
    )


class NetatmoSwitch(NetatmoModuleEntity, SwitchEntity):
    """Representation of a Netatmo switch device."""

    _attr_name = None
    _attr_configuration_url = CONF_URL_CONTROL
    device: NaModules.Switch

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
    ) -> None:
        """Initialize the Netatmo device."""
        super().__init__(netatmo_device)
        self._signal_name = f"{HOME}-{self.home.entity_id}"
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )
        self._attr_unique_id = f"{self.device.entity_id}-{self.device_type}"
        self._attr_is_on = self.device.on

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._attr_is_on = self.device.on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        await self.device.async_on()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        await self.device.async_off()
        self._attr_is_on = False
        self.async_write_ha_state()


PERSONS_ENTITY_DESCRIPTION_KEY = "presence"


class NetatmoPersonHomeSwitch(NetatmoDeviceEntity, SwitchEntity):
    """Representation of a Netatmo person home/away switch."""

    person: Person
    _attr_configuration_url = CONF_URL_SECURITY

    def __init__(self, person: NetatmoPerson) -> None:
        """Initialize the Netatmo device."""
        super().__init__(person.data_handler, person.person)
        self.person = person.person
        self._signal_name = f"{HOME}-{self.home.entity_id}"
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )
        self.entity_description = SwitchEntityDescription(
            key=PERSONS_ENTITY_DESCRIPTION_KEY, device_class=SwitchDeviceClass.SWITCH
        )
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{person.parent_id}-{PERSONS_DEVICE_IDENTIFIER_SUFFIX}")
            },
            name=f"{self.home.name} {PERSONS_DEVICE_NAME_SUFFIX}",
            manufacturer=self.device_description[0],
            model=self.device_description[1],
            configuration_url=self._attr_configuration_url,
        )
        self._attr_name = self.person.pseudo
        self._attr_unique_id = (
            f"{self.person.entity_id}-{PERSONS_ENTITY_DESCRIPTION_KEY}"
        )
        self._attr_is_on = not self.person.out_of_sight

    @property
    def device_type(self) -> DeviceType:
        """Return the device type."""
        return DeviceType.NACamera

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""

        self._attr_is_on = not self.person.out_of_sight
        self._attr_available = True
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set person home."""
        await self.home.async_set_persons_home([self.person.entity_id])
        self.person.out_of_sight = False
        self.data_handler.notify(self._signal_name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set person away."""
        await self.home.async_set_persons_away(self.person.entity_id)
        self.person.out_of_sight = True
        self.data_handler.notify(self._signal_name)
