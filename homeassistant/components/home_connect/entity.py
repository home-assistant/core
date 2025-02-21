"""Home Connect entity base class."""

from abc import abstractmethod
import contextlib
import logging
from typing import cast

from aiohomeconnect.model import EventKey, OptionKey
from aiohomeconnect.model.error import ActiveProgramNotSetError, HomeConnectError

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomeConnectApplianceData, HomeConnectCoordinator
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)


class HomeConnectEntity(CoordinatorEntity[HomeConnectCoordinator]):
    """Generic Home Connect entity (base class)."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        desc: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, (appliance.info.ha_id, EventKey(desc.key)))
        self.appliance = appliance
        self.entity_description = desc
        self._attr_unique_id = f"{appliance.info.ha_id}-{desc.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, appliance.info.ha_id)},
        )
        self.update_native_value()

    @abstractmethod
    def update_native_value(self) -> None:
        """Set the value of the entity."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_native_value()
        self.async_write_ha_state()
        _LOGGER.debug("Updated %s, new state: %s", self.entity_id, self.state)

    @property
    def bsh_key(self) -> str:
        """Return the BSH key."""
        return self.entity_description.key

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.appliance.info.connected and self._attr_available and super().available
        )


class HomeConnectOptionEntity(HomeConnectEntity):
    """Class for entities that represents program options."""

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.bsh_key in self.appliance.options

    @property
    def option_value(self) -> str | int | float | bool | None:
        """Return the state of the entity."""
        if event := self.appliance.events.get(EventKey(self.bsh_key)):
            return event.value
        return None

    async def async_set_option(self, value: str | float | bool) -> None:
        """Set an option for the entity."""
        try:
            # We try to set the active program option first,
            # if it fails we try to set the selected program option
            with contextlib.suppress(ActiveProgramNotSetError):
                await self.coordinator.client.set_active_program_option(
                    self.appliance.info.ha_id,
                    option_key=self.bsh_key,
                    value=value,
                )
                _LOGGER.debug(
                    "Updated %s for the active program, new state: %s",
                    self.entity_id,
                    self.state,
                )
                return

            await self.coordinator.client.set_selected_program_option(
                self.appliance.info.ha_id,
                option_key=self.bsh_key,
                value=value,
            )
            _LOGGER.debug(
                "Updated %s for the selected program, new state: %s",
                self.entity_id,
                self.state,
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_option",
                translation_placeholders=get_dict_from_home_connect_error(err),
            ) from err

    @property
    def bsh_key(self) -> OptionKey:
        """Return the BSH key."""
        return cast(OptionKey, self.entity_description.key)
