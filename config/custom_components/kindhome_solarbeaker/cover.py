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
from .kindhome_solarbeaker_ble import KindhomeBluetoothDevice, KindhomeSolarBeakerData

_LOGGER = logging.getLogger(__name__)

# Modify these constants according to your solar marquee's Bluetooth profile and attributes
DEVICE_ADDRESS = "XX:XX:XX:XX:XX:XX"
BLE_MARQUEE_SERVICE_UUID = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
BLE_ROLL_OUT_CHARACTERISTIC = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
BLE_ROLL_UP_CHARACTERISTIC = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"

_TODO_SOLARBEAKER_NAME = "Kindhome solarbeaker"


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the brunt platform."""
    device: KindhomeBluetoothDevice = hass.data[DOMAIN][entry.entry_id][DATA_DEVICE]
    coordinator = hass.data[DOMAIN][
        entry.entry_id
    ][DATA_COOR]

    log(_LOGGER, "async_setup_entry", device)


    log(_LOGGER, "async_setup_entry", coordinator.data)

    async_add_entities(
        [KindhomeSolarbeakerEntity(hass, coordinator, device)]
    )


class KindhomeSolarbeakerEntity(CoordinatorEntity[DataUpdateCoordinator[KindhomeSolarBeakerData]], CoverEntity):
    supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    should_poll = False
    device_class = CoverDeviceClass.SHADE

    def __init__(self, hass, coordinator: DataUpdateCoordinator[KindhomeSolarBeakerData], device: KindhomeBluetoothDevice):
        self.hass = hass
        self.device: KindhomeBluetoothDevice = device
        self.coordinator = coordinator
        self._is_open = None
        self._attr_unique_id = f"kindhome_solarbeaker_{self.device.address}"

        self._is_opening = False
        self._is_closing = False
        self._is_closed = False

    @property
    def name(self):
        return self.device.get_device_name()

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": self.name,
        }

    @property
    def available(self) -> bool:
        return self.device.available()

    @property
    def is_opening(self):
        return self._is_opening

    @property
    def is_closing(self):
        return self._is_closing

    @property
    def is_closed(self):
        return self._is_closed

    async def async_open_cover(self, **kwargs):

        self._is_closed = False
        self._is_closing = False
        self._is_opening = True
        await self.device.move_forward()
        log(_LOGGER, "async_open_cover", "opened cover")
        self.async_write_ha_state()
        log(_LOGGER, "async_open_cover", "wrote state")

    async def async_close_cover(self, **kwargs):
        """Close the marquee."""

        self._is_closed = True

        self._is_opening = False
        self._is_closing = True
        await self.device.move_backward()
        log(_LOGGER, "async_close_cover", "closed the cover")
        self.async_write_ha_state()
        log(_LOGGER, "async_close_cover", "wrote state")

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        log(_LOGGER, "async_stop_cover", "stopping the cover")

        self._is_opening = False
        self._is_closing = False
        await self.device.stop()
        self.async_write_ha_state()


    # If I want to fetch by polling
    async def request_coordinator_refresh(self) -> None:
        FAST_INTERVAL = 20
        self.coordinator.update_interval = FAST_INTERVAL
        await self.coordinator.async_request_refresh()


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
