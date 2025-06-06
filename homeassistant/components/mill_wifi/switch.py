"""Support for switch capabilities."""

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import MillApiClient
from .common_entity import MillEntity
from .const import DOMAIN
from .coordinator import MillDataCoordinator
from .device_capability import DEVICE_CAPABILITY_MAP, EDeviceCapability, EDeviceType
from .device_metric import DeviceMetric

_LOGGER = logging.getLogger(__name__)

SWITCH_TYPES: dict[
    EDeviceCapability, tuple[str, SwitchDeviceClass | None, str | None]
] = {
    EDeviceCapability.ONOFF: ("Power", SwitchDeviceClass.SWITCH, None),
    EDeviceCapability.CHILD_LOCK: ("Child Lock", None, "mdi:account-lock"),
    EDeviceCapability.COMMERCIAL_LOCK: ("Commercial Lock", None, "mdi:lock-commercial"),
    EDeviceCapability.OPEN_WINDOW: (
        "Open Window Detection",
        None,
        "mdi:window-open-variant",
    ),
    EDeviceCapability.PREDICTIVE_HEATING: (
        "Predictive Heating",
        None,
        "mdi:chart-timeline-variant",
    ),
    EDeviceCapability.PID_CONTROLLER: ("PID Controller", None, "mdi:axis-arrow-lock"),
    EDeviceCapability.SLOW_PID: ("Slow PID", None, "mdi:axis-arrow-lock"),
    EDeviceCapability.INDIVIDUAL_CONTROL: (
        "Individual Control",
        None,
        "mdi:tune-variant",
    ),
    EDeviceCapability.COOLING_MODE: ("Cooling Mode", None, "mdi:snowflake"),
    EDeviceCapability.GREE_DISPLAY_LIGHT: ("Display Light", None, "mdi:lightbulb"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Entry point."""

    coordinator: MillDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api: MillApiClient = hass.data[DOMAIN][entry.entry_id]["api"]
    entities = []

    if not coordinator.data:
        _LOGGER.warning("No data in coordinator during switch setup, skipping.")
        return

    for device_id, device_data in coordinator.data.items():
        if not device_data:
            continue

        device_type_name = DeviceMetric.get_device_type(device_data)
        if not device_type_name:
            _LOGGER.warning(
                "Could not determine device type for switch entity: %s", device_id
            )
            continue

        try:
            device_type_enum = EDeviceType(device_type_name)
        except ValueError:
            _LOGGER.warning(
                "Unsupported device type for switch platform: %s for device %s",
                device_type_name,
                device_id,
            )
            continue

        capabilities = DEVICE_CAPABILITY_MAP.get(device_type_enum, set())

        for capability_enum, (
            name_suffix,
            device_class,
            icon,
        ) in SWITCH_TYPES.items():  # Unpack icon
            if capability_enum in capabilities:
                if (
                    capability_enum == EDeviceCapability.ONOFF
                    and EDeviceCapability.TARGET_TEMPERATURE in capabilities
                    and EDeviceCapability.MEASURE_TEMPERATURE in capabilities
                ):
                    _LOGGER.debug(
                        "Skipping ONOFF switch for %s as it will be part of Climate entity.",
                        device_id,
                    )
                    continue

                entities.append(
                    MillSwitch(
                        coordinator,
                        api,
                        device_id,
                        capability_enum,
                        name_suffix,
                        device_class,
                        icon,
                    )
                )
    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.info("No switch entities added for Mill WiFi integration.")


class MillSwitch(MillEntity, SwitchEntity):
    """Switch class."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(
        self,
        coordinator: MillDataCoordinator,
        api: MillApiClient,
        device_id: str,
        capability: EDeviceCapability,
        name_suffix: str,
        device_class: SwitchDeviceClass | None,
        icon: str | None,
    ):
        """Init switch class."""

        super().__init__(coordinator, device_id, capability)
        self._api = api
        self.name = name_suffix

        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_is_on = None
        self._update_internal_state()

    def _update_internal_state(self) -> None:
        if self._device:
            new_state = DeviceMetric.get_capability_value(
                self._device, self._capability
            )

            bool_state = bool(new_state) if new_state is not None else None
            if self._attr_is_on != bool_state:
                self._attr_is_on = bool_state
        else:
            self._attr_is_on = None

    @property
    def is_on(self) -> bool | None:
        """Return on/off value."""

        return self._attr_is_on

    async def _common_switch_action(self, turn_on: bool):
        cap_name = self._capability.value if self._capability else "unknown_capability"
        if not self._device:
            _LOGGER.error(
                f"Cannot change state for {cap_name}, device data not available for {self.entity_id}."  # noqa: G004
            )
            return

        original_state = self._attr_is_on

        self._attr_is_on = turn_on
        self.async_write_ha_state()

        try:
            await self._api.set_switch_capability(
                self._device_id, self._capability.value, turn_on, self._device
            )
            self.hass.async_create_task(self._delayed_refresh(2))
        except Exception as e:  # noqa: BLE001
            _LOGGER.error(
                f"Error {'turning on' if turn_on else 'turning off'} {cap_name} for {self._device_id}: {e}"  # noqa: G004
            )
            self._attr_is_on = original_state
            self.async_write_ha_state()

    async def _delayed_refresh(self, delay_seconds: int):
        await asyncio.sleep(delay_seconds)
        if self.coordinator and self.hass:
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""

        await self._common_switch_action(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""

        await self._common_switch_action(False)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_internal_state()
        super()._handle_coordinator_update()
