"""Base class for Tado entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import TadoConnector
from .const import DEFAULT_NAME, DOMAIN, TADO_HOME, TADO_ZONE


class TadoDeviceEntity(Entity):
    """Base implementation for Tado device."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, device_info: dict[str, str]) -> None:
        """Initialize a Tado device."""
        super().__init__()
        self._device_info = device_info
        self.device_name = device_info["serialNo"]
        self.device_id = device_info["shortSerialNo"]
        self._attr_device_info = DeviceInfo(
            configuration_url=f"https://app.tado.com/en/main/settings/rooms-and-devices/device/{self.device_name}",
            identifiers={(DOMAIN, self.device_id)},
            name=self.device_name,
            manufacturer=DEFAULT_NAME,
            sw_version=device_info["currentFwVersion"],
            model=device_info["deviceType"],
            via_device=(DOMAIN, device_info["serialNo"]),
        )


class TadoHomeEntity(Entity):
    """Base implementation for Tado home."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, tado: TadoConnector) -> None:
        """Initialize a Tado home."""
        super().__init__()
        self.home_name = tado.home_name
        self.home_id = tado.home_id
        self._attr_device_info = DeviceInfo(
            configuration_url="https://app.tado.com",
            identifiers={(DOMAIN, str(tado.home_id))},
            manufacturer=DEFAULT_NAME,
            model=TADO_HOME,
            name=tado.home_name,
        )


class TadoZoneEntity(Entity):
    """Base implementation for Tado zone."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, zone_name: str, home_id: int, zone_id: int) -> None:
        """Initialize a Tado zone."""
        super().__init__()
        self.zone_name = zone_name
        self.zone_id = zone_id
        self._attr_device_info = DeviceInfo(
            configuration_url=(f"https://app.tado.com/en/main/home/zoneV2/{zone_id}"),
            identifiers={(DOMAIN, f"{home_id}_{zone_id}")},
            name=zone_name,
            manufacturer=DEFAULT_NAME,
            model=TADO_ZONE,
            suggested_area=zone_name,
        )
