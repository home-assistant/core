"""Support for Kindhome covers."""
import logging

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import log
from .const import DATA_DEVICE, DOMAIN
from .kindhome_solarbeaker_ble import (
    KindhomeSolarbeakerDevice,
    KindhomeSolarbeakerMotorState,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Kindhome Solarbeaker cover."""
    device: KindhomeSolarbeakerDevice = hass.data[DOMAIN][entry.entry_id][DATA_DEVICE]
    log(_LOGGER, "async_setup_entry", device)
    async_add_entities([KindhomeSolarbeakerCoverEntity(hass, device)])


class KindhomeSolarbeakerCoverEntity(CoverEntity):
    """Cover entity representing Kindhome Solarbeaker."""

    supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    should_poll = False
    device_class = CoverDeviceClass.AWNING

    def __init__(self, hass: HomeAssistant, device: KindhomeSolarbeakerDevice) -> None:
        """Init the Kindhome Solarbeaker device."""
        self.hass = hass
        self.device: KindhomeSolarbeakerDevice = device
        self._attr_unique_id = self.device.device_id

    @property
    def name(self):
        """Returns name of kindhome device associated with the cover."""
        return self.device.device_name

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for this entity."""
        return {
            "identifiers": {(DOMAIN, self.device.device_id)},
            "name": self.name,
        }

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return (
            self.device.state.motor_state == KindhomeSolarbeakerMotorState.MOTOR_FORWARD
        )

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return (
            self.device.state.motor_state
            == KindhomeSolarbeakerMotorState.MOTOR_BACKWARD
        )

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.device.state.motor_state == KindhomeSolarbeakerMotorState.CLOSED

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self.device.move_forward()

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self.device.move_backward()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        log(_LOGGER, "async_stop_cover", "stopping the cover")
        await self.device.stop()

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self.device.remove_callback(self.async_write_ha_state)
