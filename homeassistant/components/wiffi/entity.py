"""Component for wiffi support."""

from datetime import timedelta

from homeassistant.const import CONF_TIMEOUT
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import utcnow

from .const import CHECK_ENTITIES_SIGNAL, DEFAULT_TIMEOUT, DOMAIN, UPDATE_ENTITY_SIGNAL


def generate_unique_id(device, metric):
    """Generate a unique string for the entity."""
    return f"{device.mac_address.replace(':', '')}-{metric.name}"


class WiffiEntity(Entity):
    """Common functionality for all wiffi entities."""

    _attr_should_poll = False

    def __init__(self, device, metric, options):
        """Initialize the base elements of a wiffi entity."""
        self._id = generate_unique_id(device, metric)
        self._attr_unique_id = self._id
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device.mac_address)},
            identifiers={(DOMAIN, device.mac_address)},
            manufacturer="stall.biz",
            model=device.moduletype,
            name=f"{device.moduletype} {device.mac_address}",
            sw_version=device.sw_version,
            configuration_url=device.configuration_url,
        )
        self._attr_name = metric.description
        self._expiration_date = None
        self._value = None
        self._timeout = options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

    async def async_added_to_hass(self):
        """Entity has been added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{UPDATE_ENTITY_SIGNAL}-{self._id}",
                self._update_value_callback,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, CHECK_ENTITIES_SIGNAL, self._check_expiration_date
            )
        )

    def reset_expiration_date(self):
        """Reset value expiration date.

        Will be called by derived classes after a value update has been received.
        """
        self._expiration_date = utcnow() + timedelta(minutes=self._timeout)

    @callback
    def _update_value_callback(self, device, metric):
        """Update the value of the entity."""

    @callback
    def _check_expiration_date(self):
        """Periodically check if entity value has been updated.

        If there are no more updates from the wiffi device, the value will be
        set to unavailable.
        """
        if (
            self._value is not None
            and self._expiration_date is not None
            and utcnow() > self._expiration_date
        ):
            self._value = None
            self.async_write_ha_state()

    def _is_measurement_entity(self):
        """Measurement entities have a value in present time."""
        return (
            not self._attr_name.endswith("_gestern") and not self._is_metered_entity()
        )

    def _is_metered_entity(self):
        """Metered entities have a value that keeps increasing until reset."""
        return self._attr_name.endswith("_pro_h") or self._attr_name.endswith("_heute")
