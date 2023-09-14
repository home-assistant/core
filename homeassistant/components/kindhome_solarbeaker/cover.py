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
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import log
from .const import DATA_COOR, DATA_DEVICE, DOMAIN
from .kindhome_solarbeaker_ble import KindhomeBluetoothDevice, KindhomeSolarBeakerState, KindhomeSolarbeakerMotorState

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    device: KindhomeBluetoothDevice = hass.data[DOMAIN][entry.entry_id][DATA_DEVICE]
    log(_LOGGER, "async_setup_entry", device)
    async_add_entities(
        [KindhomeSolarbeakerEntity(hass, device)]
    )


class KindhomeSolarbeakerEntity(CoordinatorEntity[DataUpdateCoordinator[KindhomeSolarBeakerState]], CoverEntity):
    supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    should_poll = False
    device_class = CoverDeviceClass.AWNING

    def __init__(self, hass, device: KindhomeBluetoothDevice):
        self.hass = hass
        self.device: KindhomeBluetoothDevice = device
        self._attr_unique_id = self.device.device_id

    @property
    def name(self):
        return self.device.device_name

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self.device.device_id)},
            "name": self.name,
        }

    @property
    def available(self) -> bool:
        return self.device.available()

    @property
    def is_opening(self):
        return self.device.state.motor_state == KindhomeSolarbeakerMotorState.MOTOR_FORWARD

    @property
    def is_closing(self):
        return self.device.state.motor_state == KindhomeSolarbeakerMotorState.MOTOR_BACKWARD

    @property
    def is_closed(self):
        return self.device.state.motor_state == KindhomeSolarbeakerMotorState.CLOSED


    async def async_open_cover(self, **kwargs):
        await self.device.move_forward()

    async def async_close_cover(self, **kwargs):
        """Close the marquee."""
        await self.device.move_backward()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        log(_LOGGER, "async_stop_cover", "stopping the cover")
        await self.device.stop()


    # If I want to fetch by polling
    # async def request_coordinator_refresh(self) -> None:
    #     FAST_INTERVAL = 20
    #     self.coordinator.update_interval = FAST_INTERVAL
    #     await self.coordinator.async_request_refresh()


    # If Im gonna be fetching by pushing
    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        # Importantly for a push integration, the module that will be getting updates
        # needs to notify HA of changes. The dummy device has a registercallback
        # method, so to this we add the 'self.async_write_ha_state' method, to be
        # called where ever there are changes.
        # The call back registration is done once this entity is registered with HA
        # (rather than in the __init__)
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.device.remove_callback(self.async_write_ha_state)
