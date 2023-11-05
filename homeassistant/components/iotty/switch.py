"""Turn the entity on."""
import logging
from typing import Any

from iottycloud.lightswitch import LightSwitch
from iottycloud.verbs import LS_DEVICE_TYPE_UID

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import IottyProxy
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class IottyLightSwitch(SwitchEntity):
    """Haas entity class for iotty LightSwitch."""

    _attr_has_entity_name = True
    _attr_name = None

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = SwitchDeviceClass.SWITCH
    _iotty_cloud: Any
    _iotty_device: Any

    # _attr_should_poll = False

    def __init__(self, iotty: IottyProxy, iotty_device: LightSwitch) -> None:
        """Initialize the LightSwitch device."""
        _LOGGER.debug(
            "__init__ (%s) %s", iotty_device.device_type, iotty_device.device_id
        )

        super().__init__()
        self._iotty_cloud = iotty
        self._iotty_device = iotty_device

    @property
    def device_id(self) -> str:
        """Get the ID of this iotty Device."""
        return self._iotty_device.device_id

    @property
    def name(self) -> str:
        """Get the name of this iotty Device."""
        return self._iotty_device.name

    @property
    def is_on(self) -> bool:
        """Return true if the LightSwitch is on."""
        _LOGGER.debug(
            "is_on %s ? %s", self._iotty_device.device_id, self._iotty_device.is_on
        )
        return self._iotty_device.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the LightSwitch on."""
        _LOGGER.debug("[%s] async_turn_on", self._iotty_device.device_id)
        await self._iotty_cloud.command(
            self._iotty_device.device_id, self._iotty_device.cmd_turn_on()
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the LightSwitch off."""
        _LOGGER.debug("[%s] async_turn_off", self._iotty_device.device_id)
        await self._iotty_cloud.command(
            self._iotty_device.device_id, self._iotty_device.cmd_turn_off()
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Activate the iotty LightSwitch component."""
    _LOGGER.debug("async_setup_entry id is %s", config_entry.entry_id)

    iotty = hass.data[DOMAIN][config_entry.entry_id]
    _ls_list = await iotty.devices(LS_DEVICE_TYPE_UID)

    _LOGGER.info("Found %d LightSwitches", len(_ls_list))

    entities = []
    for _ls in _ls_list:
        new_entity = IottyLightSwitch(iotty, _ls)
        iotty.store_entity(_ls.device_id, new_entity)
        entities.append(new_entity)

    async_add_entities(entities)
