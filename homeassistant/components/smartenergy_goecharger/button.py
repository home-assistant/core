"""Support for go-e Charger Cloud custom buttons."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonEntity,
    ButtonEntityDescription,
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
    OFFLINE,
    ONLINE,
    STATUS,
    WALLBOX_CONTROL,
    CarStatus,
)
from .controller import ChargerController, init_service_data

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass
class BaseButtonDescription(ButtonEntityDescription):
    """Class to describe a Base button."""

    press_args: None = None


class WallboxControlButton(CoordinatorEntity, ButtonEntity):
    """Representation of a Charge Button."""

    def __init__(
        self,
        hass,
        coordinator,
        device_id,
        description,
        attribute,
    ) -> None:
        """Initialize the device."""
        super().__init__(coordinator)
        self.entity_description = description
        self.entity_id = description.key
        self._attr_unique_id = description.key
        self._device_id = device_id
        self._charger_controller: ChargerController = ChargerController(hass)
        self._attribute = attribute

    async def async_press(self) -> None:
        """Handle the button press. Start/stop charging or authenticate the user."""

        data: dict = self.coordinator.data[self._device_id]

        if data[STATUS] == OFFLINE:
            return

        # service_data = init_service_data({"device_name": self._device_id})

        if data[CAR_STATUS] == CarStatus.CAR_CHARGING:
            # car status is 2 - stop charging
            await self._charger_controller.stop_charging(
                init_service_data({"device_name": self._device_id}, "stop_charging")
            )
        elif data[CAR_STATUS] == CarStatus.CAR_CONNECTED_AUTH_REQUIRED:
            # car status is 3 - authenticate
            service_data = init_service_data(
                {"device_name": self._device_id, "status": 0}, "set_transaction"
            )
            await self._charger_controller.set_transaction(service_data)
        elif data[CAR_STATUS] == CarStatus.CHARGING_FINISHED_DISCONNECT:
            # car status is 4 - start charging
            await self._charger_controller.start_charging(
                init_service_data({"device_name": self._device_id}, "start_charging")
            )
        else:
            # car status is 1 - do nothing
            pass

    @property
    def name(self) -> str:
        """Return the name of the sensor."""

        data: dict = self.coordinator.data[self._device_id]

        if data[STATUS] == OFFLINE:
            return "Wallbox is offline"

        if data[CAR_STATUS] == CarStatus.CAR_CHARGING:
            # car status is 2 - stop charging
            return "Stop charging"
        if data[CAR_STATUS] == CarStatus.CAR_CONNECTED_AUTH_REQUIRED:
            # car status is 3 - authenticate
            return "Authenticate car"
        if data[CAR_STATUS] == CarStatus.CHARGING_FINISHED_DISCONNECT:
            # car status is 4 - start charging
            return "Start charging"

        # car status is 1 - do nothing
        return "Please connect car"

    @property
    def available(self) -> bool:
        """Make the button (un)available based on the status."""

        data: dict = self.coordinator.data[self._device_id]

        return (
            data[STATUS] == ONLINE
            and data[CAR_STATUS] != CarStatus.CHARGER_READY_NO_CAR
        )

    @property
    def unique_id(self) -> str | None:
        """Return the unique_id of the sensor."""
        return f"{self._device_id}_{self._attribute}"


def _create_buttons(
    hass: HomeAssistant, chargers: list[str]
) -> list[WallboxControlButton]:
    """Create input buttons for authentication."""
    button_entities: list[WallboxControlButton] = []

    for charger_name in chargers:
        button_entities.append(
            WallboxControlButton(
                hass,
                hass.data[DOMAIN][f"{charger_name}_coordinator"],
                charger_name,
                BaseButtonDescription(
                    key=f"{BUTTON_DOMAIN}.{DOMAIN}_{charger_name}_{WALLBOX_CONTROL}",
                    name="Wallbox control",
                    icon="mdi:battery-charging",
                ),
                WALLBOX_CONTROL,
            )
        )

    return button_entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set buttons from a config entry created in the integrations UI."""

    entry_id: str = config_entry.entry_id
    config: dict = hass.data[DOMAIN][entry_id]
    _LOGGER.debug("Setting up the go-e Charger Cloud button for=%s", entry_id)

    if config_entry.options:
        config.update(config_entry.options)

    async_add_entities(
        _create_buttons(hass, [entry_id]),
        update_before_add=True,
    )


# pylint: disable=unused-argument
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up go-e Charger Cloud Button platform."""

    _LOGGER.debug("Setting up the go-e Charger Cloud button platform")

    if discovery_info is None:
        _LOGGER.error("Missing discovery_info, skipping setup")
        return

    async_add_entities(_create_buttons(hass, discovery_info[CONF_CHARGERS]))
