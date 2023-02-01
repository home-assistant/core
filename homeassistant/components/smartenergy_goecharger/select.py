"""Support for go-e Charger Cloud custom select inputs."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CAR_STATUS,
    CONF_CHARGERS,
    DOMAIN,
    ONLINE,
    PHASE_SWITCH_MODE,
    STATUS,
    CarStatus,
)
from .controller import ChargerController, init_service_data

_LOGGER: logging.Logger = logging.getLogger(__name__)

SELECT_INPUTS: list[dict[str, Any]] = [
    {
        "id": PHASE_SWITCH_MODE,
        "name": "Set phase mode",
        "icon": "mdi:eye",
        "options": ["0", "1", "2"],
    }
]


@dataclass
class BaseSelectDescription(SelectEntityDescription):
    """Class to describe a Base select input."""

    press_args: None = None


class PhaseSelectInput(CoordinatorEntity, SelectEntity):
    """Representation of the phase mode select input."""

    def __init__(
        self,
        hass,
        device_id,
        description,
        input_props,
        options,
    ) -> None:
        """Initialize the device."""

        super().__init__(hass.data[DOMAIN][f"{device_id}_coordinator"])
        self.entity_description = description
        self.entity_id = description.key
        self._attr_unique_id = description.key
        self._device_id = device_id
        self._charger_controller: ChargerController = ChargerController(hass)
        self._attribute = input_props["id"]
        self._attr_current_option = options["current_option"]
        self._attr_options = options["regular"]
        self._attr_device_class = input_props["device_class"]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        service_data = init_service_data(
            {"device_name": self._device_id, "phase": int(option)}, "set_phase"
        )

        await self._charger_controller.set_phase(service_data)

    @property
    def current_option(self) -> str | None:
        """Return the state of the entity."""
        if self._attribute not in self.coordinator.data[self._device_id]:
            return None

        return str(self.coordinator.data[self._device_id][self._attribute])

    @property
    def unique_id(self) -> str | None:
        """Return the unique_id of the sensor."""
        return f"{self._device_id}_{self._attribute}"

    @property
    def available(self) -> bool:
        """Make the select input (un)available based on the status."""

        data: dict = self.coordinator.data[self._device_id]

        return (
            data[STATUS] == ONLINE
            and data[CAR_STATUS] != CarStatus.CHARGER_READY_NO_CAR
        )


def _create_select_inputs(
    hass: HomeAssistant, chargers: list[str]
) -> list[PhaseSelectInput]:
    """Create select inputs for defined entities."""
    select_entities: list[PhaseSelectInput] = []

    for charger_name in chargers:
        for select_input in SELECT_INPUTS:
            data: dict = hass.data[DOMAIN][f"{charger_name}_coordinator"].data[
                charger_name
            ]

            if PHASE_SWITCH_MODE not in data:
                _LOGGER.error("Data not available, won't create select inputs")
                return []

            select_entities.append(
                PhaseSelectInput(
                    hass,
                    charger_name,
                    BaseSelectDescription(
                        key=f"{SELECT_DOMAIN}.{DOMAIN}_{charger_name}_{select_input['id']}",
                        name=select_input["name"],
                        icon=select_input["icon"],
                    ),
                    {
                        "id": select_input["id"],
                        "device_class": f"{DOMAIN}__phase_switch_mode",
                    },
                    {
                        "current_option": str(data[PHASE_SWITCH_MODE]),
                        "regular": select_input["options"],
                    },
                )
            )

    return select_entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set select inputs from a config entry created in the integrations UI."""

    entry_id: str = config_entry.entry_id
    config: dict = hass.data[DOMAIN][entry_id]
    _LOGGER.debug("Setting up the go-e Charger Cloud button for=%s", entry_id)

    if config_entry.options:
        config.update(config_entry.options)

    async_add_entities(
        _create_select_inputs(hass, [entry_id]),
        update_before_add=True,
    )


# pylint: disable=unused-argument
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up go-e Charger Cloud select platform."""

    _LOGGER.debug("Setting up the go-e Charger Cloud select platform")

    if discovery_info is None:
        _LOGGER.error("Missing discovery_info, skipping setup")
        return

    async_add_entities(_create_select_inputs(hass, discovery_info[CONF_CHARGERS]))
