"""Base class for Tado entity."""
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DEFAULT_NAME, DOMAIN, TADO_HOME, TADO_ZONE


class TadoDeviceEntity(Entity):
    """Base implementation for Tado device."""

    def __init__(self, device_info):
        """Initialize a Tado device."""
        super().__init__()
        self._device_info = device_info
        self.device_name = device_info["serialNo"]
        self.device_id = device_info["shortSerialNo"]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return DeviceInfo(
            configuration_url=f"https://app.tado.com/en/main/settings/rooms-and-devices/device/{self.device_name}",
            identifiers={(DOMAIN, self.device_id)},
            name=self.device_name,
            manufacturer=DEFAULT_NAME,
            sw_version=self._device_info["currentFwVersion"],
            model=self._device_info["deviceType"],
            via_device=(DOMAIN, self._device_info["serialNo"]),
        )

    @property
    def should_poll(self):
        """Do not poll."""
        return False


class TadoHomeEntity(Entity):
    """Base implementation for Tado home."""

    def __init__(self, tado):
        """Initialize a Tado home."""
        super().__init__()
        self.home_name = tado.home_name
        self.home_id = tado.home_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return DeviceInfo(
            configuration_url="https://app.tado.com",
            identifiers={(DOMAIN, self.home_id)},
            manufacturer=DEFAULT_NAME,
            model=TADO_HOME,
            name=self.home_name,
        )


class TadoZoneEntity(Entity):
    """Base implementation for Tado zone."""

    def __init__(self, zone_name, home_id, zone_id):
        """Initialize a Tado zone."""
        super().__init__()
        self._device_zone_id = f"{home_id}_{zone_id}"
        self.zone_name = zone_name
        self.zone_id = zone_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return DeviceInfo(
            configuration_url=f"https://app.tado.com/en/main/home/zoneV2/{self.zone_id}",
            identifiers={(DOMAIN, self._device_zone_id)},
            name=self.zone_name,
            manufacturer=DEFAULT_NAME,
            model=TADO_ZONE,
            suggested_area=self.zone_name,
        )

    @property
    def should_poll(self):
        """Do not poll."""
        return False
