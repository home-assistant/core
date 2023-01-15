"""Support for iNELS buttons."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inelsmqtt.const import (
    DA3_22M,
    DA3_66M,
    FA3_612M,
    GBP3_60,
    GRT3_50,
    GSB3_20SX,
    GSB3_40SX,
    GSB3_60SX,
    GSB3_90SX,
    IDRT3_1,
    RC3_610DALI,
    SA3_02B,
    SA3_02M,
    SA3_04M,
    SA3_06M,
    SA3_012M,
    WSB3_20,
    WSB3_20H,
    WSB3_40,
    WSB3_40H,
)
from inelsmqtt.devices import Device

from homeassistant.components.button import (
    SERVICE_PRESS,
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import InelsBaseEntity
from .const import DEVICES, DOMAIN, ICON_BUTTON, ICON_MINUS, ICON_PLUS


@dataclass
class InelsButtonDescription(ButtonEntityDescription):
    """A class that describes button entity."""

    var: str | None = None
    index: int | None = None


supported_devices = [
    GRT3_50,
    DA3_22M,
    GSB3_20SX,
    GSB3_40SX,
    GSB3_60SX,
    GSB3_90SX,
    SA3_02B,
    SA3_02M,
    SA3_04M,
    SA3_06M,
    SA3_012M,
    WSB3_20H,
    DA3_66M,
    WSB3_20,
    WSB3_40,
    WSB3_40H,
    IDRT3_1,
    GBP3_60,
    RC3_610DALI,
    FA3_612M,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load iNELS buttons from config entry."""
    device_list: list[Device] = hass.data[DOMAIN][config_entry.entry_id][DEVICES]

    entities: list[InelsBaseEntity] = []

    for device in device_list:
        if device.inels_type in supported_devices:
            val = device.get_value()
            if "din" in val.ha_value.__dict__:
                for k in range(len(val.ha_value.din)):
                    entities.append(
                        InelsBusButton(
                            device=device,
                            description=InelsButtonDescription(
                                key=f"{k+1}",
                                name=f"Digital input {k+1}",
                                icon=ICON_BUTTON,
                                entity_category=EntityCategory.CONFIG,
                                var="din",
                                index=k,
                            ),
                        )
                    )
            if "sw" in val.ha_value.__dict__:
                for k in range(len(val.ha_value.sw)):
                    entities.append(
                        InelsBusButton(
                            device=device,
                            description=InelsButtonDescription(
                                key=f"{k+1}",
                                name=f"Switch {k+1}",
                                icon=ICON_BUTTON,
                                entity_category=EntityCategory.CONFIG,
                                # only if needed
                                var="sw",
                                index=k,
                            ),
                        )
                    )
            if "plusminus" in val.ha_value.__dict__:
                for k in range(len(val.ha_value.plusminus)):
                    entities.append(
                        InelsBusButton(
                            device=device,
                            description=InelsButtonDescription(
                                key=f"{k+1}",
                                name="Plus" if k == 0 else "Minus",
                                icon=ICON_PLUS if k == 0 else ICON_MINUS,
                                entity_category=EntityCategory.CONFIG,
                                var="plusminus",
                                index=k,
                            ),
                        )
                    )
        elif device.device_type == Platform.BUTTON:
            index = 1
            val = device.get_value()
            if val.ha_value is not None:
                while index <= val.ha_value.amount:
                    entities.append(
                        InelsButton(
                            device=device,
                            description=InelsButtonDescription(
                                key=f"{index}",
                                name=f"Button {index}",
                                icon=ICON_BUTTON,
                                entity_category=EntityCategory.CONFIG,
                            ),
                        )
                    )
                    index += 1

    async_add_entities(entities)


class InelsButton(InelsBaseEntity, ButtonEntity):
    """Button switch can be toggled using with MQTT."""

    entity_description: InelsButtonDescription
    _attr_device_class: ButtonDeviceClass | None = None

    def __init__(self, device: Device, description: InelsButtonDescription) -> None:
        """Initialize a button."""
        super().__init__(device=device)
        self.entity_description = description

        self._attr_unique_id = f"{self._attr_unique_id}-{description.key}"

        if description.name:
            self._attr_name = f"{self._attr_name} {description.name}"

    def _callback(self, new_value: Any) -> None:
        super()._callback(new_value)
        entity_id = f"{Platform.BUTTON}.{self._device_id}_btn_{self._device.values.ha_value.number}"

        if (
            self._device.values.ha_value.pressing
            and self._device.values.ha_value.number == int(self.entity_description.key)
        ):
            self.hass.services.call(
                Platform.BUTTON,
                SERVICE_PRESS,
                {ATTR_ENTITY_ID: entity_id},
                True,
                self._context,
            )

    def press(self) -> None:
        """Press the button."""


class InelsBusButton(InelsBaseEntity, ButtonEntity):
    """Button switch that can be toggled by MQTT. Specific version for Bus devices."""

    entity_description: InelsButtonDescription
    _attr_device_class: ButtonDeviceClass | None = None

    def __init__(self, device: Device, description: InelsButtonDescription) -> None:
        """Initialize button."""
        super().__init__(device=device)
        self.entity_description = description

        self._attr_unique_id = f"{self._attr_unique_id}-{description.name}"

        if description.name:
            self._attr_name = f"{self._attr_name} {description.name}"

    def _callback(self, new_value: Any) -> None:
        super()._callback(new_value)
        key_index = int(self.entity_description.key)
        if self.entity_description.var != "plusminus":
            entity_id = f"{Platform.BUTTON}.{self._device_id}_{self.entity_description.var}_{key_index}"
        else:
            name = "plus" if key_index == 1 else "minus"
            entity_id = f"{Platform.BUTTON}.{self._device_id}_{name}"

        curr_val = self._device.values.ha_value
        last_val = self._device.last_values.ha_value
        if (
            curr_val.__dict__[self.entity_description.var][
                self.entity_description.index
            ]
            and not last_val.__dict__[self.entity_description.var][
                self.entity_description.index
            ]
        ):
            self.hass.services.call(
                Platform.BUTTON,
                SERVICE_PRESS,
                {ATTR_ENTITY_ID: entity_id},
                True,
                self._context,
            )

    def press(self) -> None:
        """Press the button."""
