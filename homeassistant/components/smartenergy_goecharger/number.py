"""Support for go-e Charger Cloud custom number inputs."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CAR_STATUS,
    CHARGER_MAX_CURRENT,
    CONF_CHARGERS,
    DOMAIN,
    MAX_CHARGING_CURRENT_LIMIT,
    MIN_CHARGING_CURRENT_LIMIT,
    ONLINE,
    STATUS,
    CarStatus,
)
from .controller import ChargerController, init_service_data

_LOGGER: logging.Logger = logging.getLogger(__name__)

NUMBER_INPUTS: list[dict[str, str]] = [
    {
        "id": CHARGER_MAX_CURRENT,
        "name": "Set charging speed",
        "icon": "mdi:current-ac",
    }
]


@dataclass
class BaseNumberDescription(NumberEntityDescription):
    """Class to describe a Base number input."""

    press_args: None = None


class CurrentInputNumber(CoordinatorEntity, NumberEntity):
    """Representation of the current number input."""

    def __init__(
        self,
        hass,
        device_id,
        description,
        input_props,
    ) -> None:
        """Initialize the device."""

        super().__init__(hass.data[DOMAIN][f"{device_id}_coordinator"])
        self.entity_description = description
        self.entity_id: str = description.key
        self._attr_unique_id = description.key
        self._device_id = device_id
        self._charger_controller: ChargerController = ChargerController(hass)
        self._attribute: str = input_props["id"]
        self._min: int = input_props["min"]
        self._max: int = input_props["max"]
        self._step: int = input_props["step"]

    @property
    def native_max_value(self) -> float:
        """Return the maximum available current."""
        return self._max

    @property
    def native_min_value(self) -> float:
        """Return the minimum available current."""
        return self._min

    @property
    def native_step(self) -> float:
        """Return the available step number."""
        return self._step

    @property
    def native_value(self) -> float | None:
        """Return the value of the entity."""
        return self.coordinator.data[self._device_id][self._attribute]

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the entity."""
        service_data = init_service_data(
            {"device_name": self._device_id, "charging_power": int(value)},
            "change_charging_power",
        )

        await self._charger_controller.change_charging_power(service_data)

    @property
    def unique_id(self) -> str | None:
        """Return the unique_id of the sensor."""
        return f"{self._device_id}_{self._attribute}"

    @property
    def available(self) -> bool:
        """Make the number input (un)available based on the status."""

        data: dict = self.coordinator.data[self._device_id]

        return (
            data[STATUS] == ONLINE
            and data[CAR_STATUS] != CarStatus.CHARGER_READY_NO_CAR
        )


def _create_input_numbers(
    hass: HomeAssistant, chargers: list[str]
) -> list[CurrentInputNumber]:
    """Create input number sliders for defined entities."""
    number_entities: list[CurrentInputNumber] = []

    for charger_name in chargers:
        data: dict = hass.data[DOMAIN][f"{charger_name}_coordinator"].data[charger_name]

        if (
            MIN_CHARGING_CURRENT_LIMIT not in data
            or MAX_CHARGING_CURRENT_LIMIT not in data
        ):
            _LOGGER.error("Data not available, won't create number inputs")
            return []

        min_limit: int = data[MIN_CHARGING_CURRENT_LIMIT]
        max_limit: int = data[MAX_CHARGING_CURRENT_LIMIT]

        if min_limit >= max_limit:
            _LOGGER.error(
                "Min limit is greater than/equal to the max limit, can't configure the number input"
            )
        else:
            for number_input in NUMBER_INPUTS:
                number_entities.append(
                    CurrentInputNumber(
                        hass,
                        charger_name,
                        BaseNumberDescription(
                            key=f"{NUMBER_DOMAIN}.{DOMAIN}_{charger_name}_{number_input['id']}",
                            name=number_input["name"],
                            icon=number_input["icon"],
                        ),
                        {
                            "id": number_input["id"],
                            "min": min_limit,
                            "max": max_limit,
                            "step": 1,
                        },
                    )
                )

    return number_entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set number inputs from a config entry created in the integrations UI."""

    entry_id: str = config_entry.entry_id
    config: dict = hass.data[DOMAIN][entry_id]
    _LOGGER.debug("Setting up the go-e Charger Cloud button for=%s", entry_id)

    if config_entry.options:
        config.update(config_entry.options)

    async_add_entities(
        _create_input_numbers(hass, [entry_id]),
        update_before_add=True,
    )


# pylint: disable=unused-argument
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up go-e Charger Cloud number platform."""

    _LOGGER.debug("Setting up the go-e Charger Cloud number platform")

    if discovery_info is None:
        _LOGGER.error("Missing discovery_info, skipping setup")
        return

    async_add_entities(_create_input_numbers(hass, discovery_info[CONF_CHARGERS]))
