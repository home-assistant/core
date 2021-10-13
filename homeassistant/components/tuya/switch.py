"""Support for Tuya switches."""
from __future__ import annotations

from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import TuyaHaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode

# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
TUYA_SUPPORT_TYPE = {
    "kg",  # Switch
    "cz",  # Socket
    "pc",  # Power Strip
    "bh",  # Smart Kettle
    "dlq",  # Breaker
    "cwysj",  # Pet Water Feeder
    "kj",  # Air Purifier
    "xxj",  # Diffuser
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya sensors dynamically through tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered tuya sensor."""
        async_add_entities(
            _setup_entities(hass, entry, hass_data.device_manager, device_ids)
        )

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


def _setup_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_manager: TuyaDeviceManager,
    device_ids: list[str],
) -> list[TuyaHaSwitch]:
    """Set up Tuya Switch device."""
    entities: list[TuyaHaSwitch] = []
    for device_id in device_ids:
        device = device_manager.device_map[device_id]
        if device is None or device.category not in TUYA_SUPPORT_TYPE:
            continue

        for function in device.function:
            if device.category == "kj":
                if function in [
                    DPCode.ANION,
                    DPCode.FILTER_RESET,
                    DPCode.LIGHT,
                    DPCode.LOCK,
                    DPCode.UV,
                    DPCode.WET,
                ]:
                    entities.append(TuyaHaSwitch(device, device_manager, function))

            elif device.category == "cwysj":
                if (
                    function
                    in [
                        DPCode.FILTER_RESET,
                        DPCode.UV,
                        DPCode.PUMP_RESET,
                        DPCode.WATER_RESET,
                    ]
                    or function.startswith(DPCode.SWITCH)
                ):
                    entities.append(TuyaHaSwitch(device, device_manager, function))

            elif function.startswith(DPCode.START) or function.startswith(
                DPCode.SWITCH
            ):
                entities.append(TuyaHaSwitch(device, device_manager, function))

    return entities


class TuyaHaSwitch(TuyaHaEntity, SwitchEntity):
    """Tuya Switch Device."""

    dp_code_switch = DPCode.SWITCH
    dp_code_start = DPCode.START

    def __init__(
        self, device: TuyaDevice, device_manager: TuyaDeviceManager, dp_code: str = ""
    ) -> None:
        """Init TuyaHaSwitch."""
        super().__init__(device, device_manager)

        self.dp_code = dp_code
        self.channel = (
            dp_code.replace(DPCode.SWITCH, "")
            if dp_code.startswith(DPCode.SWITCH)
            else dp_code
        )
        self._attr_unique_id = f"{super().unique_id}{self.channel}"

    @property
    def name(self) -> str | None:
        """Return Tuya device name."""
        return f"{self.tuya_device.name}{self.channel}"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.tuya_device.status.get(self.dp_code, False)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._send_command([{"code": self.dp_code, "value": True}])

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._send_command([{"code": self.dp_code, "value": False}])
