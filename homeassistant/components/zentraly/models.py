"""Home Assistant runtime and registry information for Zentraly."""

from dataclasses import dataclass

from zentraly import ZentralyApi, ZentralyDevice as LibraryDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


@dataclass(slots=True)
class ZentralyDevice(LibraryDevice):
    """Adapt a library device to Home Assistant's device registry."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant device information."""

        device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self.device_id,
                )
            },
            connections={
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self.mac,
                )
            },
            manufacturer="Zentraly",
            model=self.model,
            model_id=self.device_model.name,
            name=self.device_id,
            serial_number=self.device_id,
            configuration_url=self.configuration_url,
        )

        if self.firmware_version is not None:
            device_info["sw_version"] = self.firmware_version

        if self.hardware_version is not None:
            device_info["hw_version"] = self.hardware_version

        return device_info


@dataclass(slots=True)
class ZentralyData:
    """Runtime data for Zentraly."""

    api: ZentralyApi
    device: ZentralyDevice


type ZentralyConfigEntry = ConfigEntry[ZentralyData]
