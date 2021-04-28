"""Code to handle a Xiaomi Gateway."""
import logging

from micloud import MiCloud
from miio import DeviceException, gateway

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_AVAILABLE,
    CONF_CLOUD_COUNTRY,
    CONF_CLOUD_PASSWORD,
    CONF_CLOUD_SUBDEVICES,
    CONF_CLOUD_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ConnectXiaomiGateway:
    """Class to async connect to a Xiaomi Gateway."""

    def __init__(self, hass, config_entry):
        """Initialize the entity."""
        self._hass = hass
        self._config_entry = config_entry
        self._gateway_device = None
        self._gateway_info = None

    @property
    def gateway_device(self):
        """Return the class containing all connections to the gateway."""
        return self._gateway_device

    @property
    def gateway_info(self):
        """Return the class containing gateway info."""
        return self._gateway_info

    async def async_connect_gateway(self, host, token):
        """Connect to the Xiaomi Gateway."""
        _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

        use_cloud = self._config_entry.options.get(CONF_CLOUD_SUBDEVICES, False)
        cloud_username = self._config_entry.options.get(CONF_CLOUD_USERNAME)
        cloud_password = self._config_entry.options.get(CONF_CLOUD_PASSWORD)
        cloud_country = self._config_entry.options.get(CONF_CLOUD_COUNTRY)

        try:
            self._gateway_device = gateway.Gateway(host, token)
            # get the gateway info
            self._gateway_info = await self._hass.async_add_executor_job(
                self._gateway_device.info
            )

            # get the connected sub devices
            if (
                use_cloud
                and cloud_username is not None
                and cloud_password is not None
                and cloud_country is not None
            ):
                # use miio-cloud
                miio_cloud = MiCloud(cloud_username, cloud_password)
                if not await self._hass.async_add_executor_job(miio_cloud.login):
                    _LOGGER.error(
                        "Could not login to Xioami Miio Cloud, check the credentials"
                    )
                    return False
                devices_raw = await self._hass.async_add_executor_job(
                    miio_cloud.get_devices, cloud_country
                )
                await self._hass.async_add_executor_job(
                    self._gateway_device.get_devices_from_dict, devices_raw
                )
            else:
                # use local query (not supported by all gateway types)
                await self._hass.async_add_executor_job(
                    self._gateway_device.discover_devices
                )

        except DeviceException:
            _LOGGER.error(
                "DeviceException during setup of xiaomi gateway with host %s", host
            )
            return False
        _LOGGER.debug(
            "%s %s %s detected",
            self._gateway_info.model,
            self._gateway_info.firmware_version,
            self._gateway_info.hardware_version,
        )
        return True


class XiaomiGatewayDevice(CoordinatorEntity, Entity):
    """Representation of a base Xiaomi Gateway Device."""

    def __init__(self, coordinator, sub_device, entry):
        """Initialize the Xiaomi Gateway Device."""
        super().__init__(coordinator)
        self._sub_device = sub_device
        self._entry = entry
        self._unique_id = sub_device.sid
        self._name = f"{sub_device.name} ({sub_device.sid})"

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def device_info(self):
        """Return the device info of the gateway."""
        return {
            "identifiers": {(DOMAIN, self._sub_device.sid)},
            "via_device": (DOMAIN, self._entry.unique_id),
            "manufacturer": "Xiaomi",
            "name": self._sub_device.name,
            "model": self._sub_device.model,
            "sw_version": self._sub_device.firmware_version,
        }

    @property
    def available(self):
        """Return if entity is available."""
        if self.coordinator.data is None:
            return False

        return self.coordinator.data[self._sub_device.sid][ATTR_AVAILABLE]
