"""Base entity for the Dio Chacon entity."""

from dio_chacon_wifi_api import DIOChaconAPIClient

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER


class DioChaconEntity:
    """Implements a common class elements representing the Dio Chacon entity."""

    def __init__(
        self,
        dio_chacon_client: DIOChaconAPIClient,
        target_id: str,
        name: str,
        model: str,
    ) -> None:
        """Initialize Dio Chacon entity."""

        self.dio_chacon_client: DIOChaconAPIClient = dio_chacon_client

        self.target_id: str | None = target_id
        self._attr_unique_id: str | None = target_id
        self._attr_name: str | None = name
        self._attr_device_info: DeviceInfo | None = DeviceInfo(
            identifiers={(DOMAIN, self.target_id)},
            manufacturer=MANUFACTURER,
            name=name,
            model=model,
        )
