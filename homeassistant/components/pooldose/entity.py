"""Base entity for Seko Pooldose integration."""

from __future__ import annotations

from typing import Literal

from pooldose.type_definitions import DeviceInfoDict, ValueDict

from homeassistant.const import CONF_MAC
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import PooldoseCoordinator


def device_info(
    info: DeviceInfoDict | None, unique_id: str, mac: str | None = None
) -> DeviceInfo:
    """Create device info for PoolDose devices."""
    if info is None:
        info = {}

    api_version = (info.get("API_VERSION") or "").removesuffix("/")

    return DeviceInfo(
        identifiers={(DOMAIN, unique_id)},
        manufacturer=MANUFACTURER,
        model=info.get("MODEL") or None,
        model_id=info.get("MODEL_ID") or None,
        name=info.get("NAME") or None,
        serial_number=unique_id,
        sw_version=(
            f"{info.get('FW_VERSION')} (SW v{info.get('SW_VERSION')}, API {api_version})"
            if info.get("FW_VERSION") and info.get("SW_VERSION") and api_version
            else None
        ),
        hw_version=info.get("FW_CODE") or None,
        configuration_url=(
            f"http://{info['IP']}/index.html" if info.get("IP") else None
        ),
        connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
    )


class PooldoseEntity(CoordinatorEntity[PooldoseCoordinator]):
    """Base class for all PoolDose entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PooldoseCoordinator,
        serial_number: str,
        device_properties: DeviceInfoDict,
        entity_description: EntityDescription,
        platform_name: Literal["sensor", "switch", "number", "binary_sensor", "select"],
    ) -> None:
        """Initialize PoolDose entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.platform_name = platform_name
        self._attr_unique_id = f"{serial_number}_{entity_description.key}"
        self._attr_device_info = device_info(
            device_properties,
            serial_number,
            coordinator.config_entry.data.get(CONF_MAC),
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.get_data() is not None

    def get_data(self) -> ValueDict | None:
        """Get data for this entity, only if available."""
        platform_data = self.coordinator.data[self.platform_name]
        return platform_data.get(self.entity_description.key)

    async def _async_perform_write(
        self, api_call, key: str, value: bool | str | float
    ) -> None:
        """Perform a write call to the API with unified error handling.

        - `api_call` should be a bound coroutine function like
          `self.coordinator.client.set_number`.
        - Raises ServiceValidationError on connection errors or when the API
          returns False.
        """
        if not await api_call(key, value):
            if not self.coordinator.client.is_connected:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="cannot_connect"
                )

            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="write_rejected",
                translation_placeholders={
                    "entity": self.entity_description.key,
                    "value": str(value),
                },
            )
