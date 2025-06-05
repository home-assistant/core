"""Support for select capabilities."""

import asyncio
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import MillApiClient
from .common_entity import MillEntity
from .const import DOMAIN, PURIFIER_FAN_MODES
from .coordinator import MillDataCoordinator
from .device_capability import DEVICE_CAPABILITY_MAP, EDeviceCapability, EDeviceType
from .device_metric import DeviceMetric

_LOGGER = logging.getLogger(__name__)

SELECT_TYPES: dict[EDeviceCapability, tuple[str, list[str]]] = {
    EDeviceCapability.PURIFIER_MODE: ("Mode", list(PURIFIER_FAN_MODES.keys())),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Entry point."""
    coordinator: MillDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api: MillApiClient = hass.data[DOMAIN][entry.entry_id]["api"]
    entities = []

    if not coordinator.data:
        _LOGGER.warning("No data in coordinator during select setup.")
        return

    for device_id, device_data in coordinator.data.items():
        if not device_data:
            continue

        device_type_name = DeviceMetric.get_device_type(device_data)
        if not device_type_name:
            _LOGGER.warning(
                "Could not determine device type for select entity: %s", device_id
            )
            continue

        try:
            device_type_enum = EDeviceType(device_type_name)
        except ValueError:
            _LOGGER.warning(
                "Unsupported device type for select entity: %s for device %s",
                device_type_name,
                device_id,
            )
            continue

        capabilities = DEVICE_CAPABILITY_MAP.get(device_type_enum, set())

        for cap_enum, (name_suffix, options) in SELECT_TYPES.items():
            if cap_enum in capabilities:
                entities.append(
                    MillSelect(
                        coordinator, api, device_id, cap_enum, name_suffix, options
                    )
                )
    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.info("No select entities added.")


class MillSelect(MillEntity, SelectEntity):
    """Select class."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(
        self,
        coordinator: MillDataCoordinator,
        api: MillApiClient,
        device_id: str,
        capability: EDeviceCapability,
        name_suffix: str,
        options: list[str],
    ):
        """Init select class."""

        super().__init__(coordinator, device_id, capability)
        self._api = api
        self.name = name_suffix

        self._attr_options = options
        self._attr_current_option = None
        self._update_internal_state()

    def _update_internal_state(self) -> None:
        if not self._device:
            self._attr_current_option = None
            return

        value = DeviceMetric.get_capability_value(self._device, self._capability)

        str_value = str(value) if value is not None else None

        if str_value in self._attr_options:
            if self._attr_current_option != str_value:
                self._attr_current_option = str_value
        elif str_value is not None:
            _LOGGER.warning(
                "Device %s reported purifier mode '%s' which is not in defined options %s. Sensor may show unknown state.",
                self.entity_id,
                str_value,
                self._attr_options,
            )

            if self._attr_current_option is not None:
                self._attr_current_option = None
        elif self._attr_current_option is not None:
            self._attr_current_option = None

    @property
    def current_option(self) -> str | None:
        """Return current option."""

        return self._attr_current_option

    async def _delayed_refresh(self, delay_seconds: int):
        await asyncio.sleep(delay_seconds)
        if self.coordinator and self.hass:
            await self.coordinator.async_request_refresh()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if not self._device:
            _LOGGER.error(
                "Cannot select option for %s, device data not available.",
                self.entity_id,
            )
            return

        _LOGGER.info(
            "Attempting to set purifier mode to: %s for device %s",
            option,
            self._device_id,
        )

        original_option = self._attr_current_option
        self._attr_current_option = option
        self.async_write_ha_state()

        try:
            await self._api.set_select_capability(
                self._device_id, self._capability.value, option, self._device
            )
            self.hass.async_create_task(self._delayed_refresh(3))
        except Exception as e:  # noqa: BLE001
            _LOGGER.error(
                "Error selecting option '%s' for %s on %s: %s",
                option,
                self._capability.value,
                self._device_id,
                e,
            )
            self._attr_current_option = original_option
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_internal_state()
        super()._handle_coordinator_update()
