"""iNELS binary sensor entity."""
from __future__ import annotations

from dataclasses import dataclass

from inelsmqtt.const import (
    DA3_22M,
    DA3_66M,
    DMD3_1,
    GRT3_50,
    GSB3_90SX,
    IM3_20B,
    IM3_40B,
    IM3_80B,
    IM3_140M,
)
from inelsmqtt.devices import Device

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import InelsBaseEntity
from .const import (
    DEVICES,
    DOMAIN,
    ICON_ALERT,
    ICON_BINARY_INPUT,
    ICON_HEAT_WAVE,
    ICON_PROXIMITY,
    LOGGER,
)


@dataclass
class InelsBinarySensorEntityDescriptionMixin:
    """Mixin keys."""


@dataclass
class InelsBinarySensorEntityDescription(
    BinarySensorEntityDescription, InelsBinarySensorEntityDescriptionMixin
):
    """Class for describing binary sensor iNELS entities."""

    var: str = ""
    index: int | None = None


supported = [
    GSB3_90SX,
    DA3_22M,
    DA3_66M,
    GRT3_50,
    IM3_80B,
    IM3_140M,
    IM3_20B,
    IM3_40B,
    DMD3_1,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load iNELS binary sensor."""
    device_list: list[Device] = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    entities: list[InelsBaseEntity] = []

    for device in device_list:
        val = device.get_value()
        if device.inels_type in supported:
            if "toa" in val.ha_value.__dict__:
                for k in range(len(val.ha_value.toa)):
                    entities.append(
                        InelsBinarySensor(
                            device=device,
                            description=InelsBinarySensorEntityDescription(
                                key=f"{k+1}",
                                name=f"Thermal overload alarm {k+1}",
                                icon=ICON_ALERT,
                                index=k,
                                var="toa",
                            ),
                        )
                    )
            if "coa" in val.ha_value.__dict__:
                for k in range(len(val.ha_value.coa)):
                    entities.append(
                        InelsBinarySensor(
                            device=device,
                            description=InelsBinarySensorEntityDescription(
                                key=f"{k+1}",
                                name=f"Current overload alarm {k+1}",
                                icon=ICON_ALERT,
                                index=k,
                                var="coa",
                            ),
                        )
                    )
            if "prox" in val.ha_value.__dict__:
                entities.append(
                    InelsBinarySensor(
                        device=device,
                        description=InelsBinarySensorEntityDescription(
                            key=" ",
                            name="Proximity sensor",
                            icon=ICON_PROXIMITY,
                            var="prox",
                        ),
                    )
                )
            if "input" in val.ha_value.__dict__:
                for k in range(len(val.ha_value.input)):
                    entities.append(
                        InelsBinaryInputSensor(
                            device=device,
                            description=InelsBinarySensorEntityDescription(
                                key=f"{k}",
                                name="Binary input sensor",
                                icon=ICON_BINARY_INPUT,
                                var="input",
                                index=k,
                            ),
                        )
                    )
            if "heating_out" in val.ha_value.__dict__:
                entities.append(
                    InelsBinaryInputSensor(
                        device=device,
                        description=InelsBinarySensorEntityDescription(
                            key="heating_out",
                            name="Heating output",
                            icon=ICON_HEAT_WAVE,
                            var="heating_out",
                        ),
                    )
                )

    async_add_entities(entities, True)


class InelsBinarySensor(InelsBaseEntity, BinarySensorEntity):
    """The platform class for binary sensors for home assistant."""

    entity_description: InelsBinarySensorEntityDescription

    def __init__(
        self,
        device: Device,
        description: InelsBinarySensorEntityDescription,
    ) -> None:
        """Initialize a binary sensor."""
        super().__init__(device=device)

        self.entity_description = description

        if self.entity_description.index:
            self._attr_unique_id = f"{self._attr_unique_id}-{self.entity_description.var}-{self.entity_description.index}"
        else:
            self._attr_unique_id = (
                f"{self._attr_unique_id}-{self.entity_description.var}"
            )

        self._attr_name = f"{self._attr_name}-{self.entity_description.name}"

    @property
    def unique_id(self) -> str | None:
        """Return unique_id of the entity."""
        return super().unique_id

    @property
    def name(self) -> str | None:
        """Return name of the entity."""
        return super().name

    @property
    def is_on(self) -> bool | None:
        """Return true is sensor is on."""
        if self.entity_description.index:
            return self._device.values.ha_value.__dict__[self.entity_description.var][
                self.entity_description.index
            ]

        return self._device.values.ha_value.__dict__[self.entity_description.var]


class InelsBinaryInputSensor(InelsBaseEntity, BinarySensorEntity):
    """The platform class for binary sensors of binary values for home assistant."""

    entity_description: InelsBinarySensorEntityDescription

    def __init__(
        self, device: Device, description: InelsBinarySensorEntityDescription
    ) -> None:
        """Initialize a binary sensor."""
        super().__init__(device=device)

        self.entity_description = description

        self._attr_unique_id = f"{self._attr_unique_id}-{self.entity_description.var}"
        if self.entity_description.index:
            self._attr_unique_id = (
                f"{self._attr_unique_id}-{self.entity_description.index}"
            )

        self._attr_name = f"{self._attr_name} {self.entity_description.name}"
        if self.entity_description.index:
            self._attr_name = f"{self._attr_name} {self.entity_description.index + 1}"

    @property
    def available(self) -> bool:
        """Return availability of device."""
        val = self._device.values.ha_value.__dict__[self.entity_description.var][
            self.entity_description.index
        ]

        last_val = self._device.last_values.ha_value.__dict__[
            self.entity_description.var
        ][self.entity_description.index]

        if val in [0, 1]:
            return True
        if last_val != val:
            if val == 2:
                LOGGER.warning("%s ALERT", self._attr_unique_id)
            elif val == 3:
                LOGGER.warning("%s TAMPER", self._attr_unique_id)
        return False

    @property
    def unique_id(self) -> str | None:
        """Return unique_id of the entity."""
        return super().unique_id

    @property
    def name(self) -> str | None:
        """Return name of the entity."""
        return super().name

    @property
    def is_on(self) -> bool | None:
        """Return true is sensor is on."""
        if self.entity_description.index:
            return (
                self._device.values.ha_value.__dict__[self.entity_description.var][
                    self.entity_description.index
                ]
                == 1
            )

        return self._device.values.ha_value.__dict__[self.entity_description.var] == 1
