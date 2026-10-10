"""Viessmann ViCare select device."""

from contextlib import suppress
from typing import override

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ViCareEntity
from .types import ViCareConfigEntry, ViCareDevice
from .utils import is_supported

# Map API values to snake_case for HA, and back
DHW_MODE_API_TO_HA: dict[str, str] = {
    "efficient": "efficient",
    "efficientWithMinComfort": "efficient_with_min_comfort",
    "off": "off",
}
DHW_MODE_HA_TO_API: dict[str, str] = {v: k for k, v in DHW_MODE_API_TO_HA.items()}


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareDHWOperatingModeSelect]:
    """Create ViCare select entities for a device."""
    return [
        ViCareDHWOperatingModeSelect(
            device.serial,
            device.config,
            device.api,
        )
        for device in device_list
        if is_supported(
            "dhw_operating_mode",
            lambda api: api.getDomesticHotWaterActiveOperatingMode(),
            device.api,
        )
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ViCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ViCare select platform."""
    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            config_entry.runtime_data.devices,
        )
    )


class ViCareDHWOperatingModeSelect(ViCareEntity, SelectEntity):
    """Representation of the ViCare DHW operating mode select entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "dhw_operating_mode"

    def __init__(
        self,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
    ) -> None:
        """Initialize the DHW operating mode select entity."""
        super().__init__("dhw_operating_mode", device_serial, device_config, device)
        self._attr_options = [
            DHW_MODE_API_TO_HA.get(mode, mode)
            for mode in device.getDomesticHotWaterOperatingModes()
        ]
        active = device.getDomesticHotWaterActiveOperatingMode()
        self._attr_current_option = DHW_MODE_API_TO_HA.get(active, active)

    def update(self) -> None:
        """Update state from the ViCare API."""
        with self.vicare_api_handler():
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_options = [
                    DHW_MODE_API_TO_HA.get(mode, mode)
                    for mode in self._api.getDomesticHotWaterOperatingModes()
                ]

            with suppress(PyViCareNotSupportedFeatureError):
                active = self._api.getDomesticHotWaterActiveOperatingMode()
                self._attr_current_option = DHW_MODE_API_TO_HA.get(active, active)

    @override
    def select_option(self, option: str) -> None:
        """Set the DHW operating mode."""
        api_mode = DHW_MODE_HA_TO_API.get(option, option)
        self._api.setDomesticHotWaterOperatingMode(api_mode)
        self._attr_current_option = option
        self.schedule_update_ha_state()
