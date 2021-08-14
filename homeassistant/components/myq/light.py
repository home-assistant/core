"""Support for MyQ-Enabled lights."""
import logging

from pymyq.const import (
    DEVICE_STATE as MYQ_DEVICE_STATE,
    DEVICE_STATE_ONLINE as MYQ_DEVICE_STATE_ONLINE,
    KNOWN_MODELS,
    MANUFACTURER,
)
from pymyq.errors import MyQError

from homeassistant.components.light import LightEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MYQ_COORDINATOR, MYQ_GATEWAY, MYQ_TO_HASS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mysq covers."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    myq = data[MYQ_GATEWAY]
    coordinator = data[MYQ_COORDINATOR]

    async_add_entities(
        [MyQDevice(coordinator, device) for device in myq.lamps.values()], True
    )


class MyQDevice(CoordinatorEntity, LightEntity):
    """Representation of a MyQ light."""

    def __init__(self, coordinator, device):
        """Initialize with API object, device id."""
        super().__init__(coordinator)
        self._device = device

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return self._device.name

    @property
    def available(self):
        """Return if the device is online."""
        if not self.coordinator.last_update_success:
            return False

        # Not all devices report online so assume True if its missing
        return self._device.device_json[MYQ_DEVICE_STATE].get(
            MYQ_DEVICE_STATE_ONLINE, True
        )

    @property
    def is_on(self):
        """Return true if the light is on, else False."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_ON

    @property
    def is_off(self):
        """Return true if the light is off, else False."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_OFF

    @property
    def supported_features(self):
        """Flag supported features."""
        return 0

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._device.device_id

    async def async_turn_on(self, **kwargs):
        """Issue on command to light."""
        if self.is_on:
            return

        try:
            await self._device.turnon(wait_for_state=True)
        except MyQError as err:
            raise HomeAssistantError(f"Turning light {self._device.name} on failed with error: {err}") from err

            return

        # Write new state to HASS
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Issue off command to light."""
        if self.is_off:
            return

        try:
            await self._device.turnoff(wait_for_state=True)
        except MyQError as err:
            _LOGGER.error(
                "Turning light %s off failed with error: %s",
                self._device.name,
                str(err),
            )

            return

        # Write opening state to HASS
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return the device_info of the device."""
        device_info = {
            "identifiers": {(DOMAIN, self._device.device_id)},
            "name": self._device.name,
            "manufacturer": MANUFACTURER,
            "sw_version": self._device.firmware_version,
        }
        model = KNOWN_MODELS.get(self._device.device_id[2:4])
        if model:
            device_info["model"] = model
        if self._device.parent_device_id:
            device_info["via_device"] = (DOMAIN, self._device.parent_device_id)
        return device_info

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
