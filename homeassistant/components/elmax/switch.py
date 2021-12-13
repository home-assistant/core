"""Elmax switch platform."""
from typing import Any

from elmax_api.model.command import SwitchCommand
from elmax_api.model.panel import PanelStatus

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType

from . import ElmaxCoordinator
from .common import ElmaxEntity
from .const import DOMAIN


class ElmaxSwitch(ElmaxEntity, SwitchEntity):
    """Implement the Elmax switch entity."""

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self.transitory_state is not None:
            return self.transitory_state
        return self._device.opened

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        client = self._coordinator.http_client
        await client.execute_command(
            endpoint_id=self._device.endpoint_id, command=SwitchCommand.TURN_ON
        )
        self.transitory_state = True
        await self.async_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        client = self._coordinator.http_client
        await client.execute_command(
            endpoint_id=self._device.endpoint_id, command=SwitchCommand.TURN_OFF
        )
        self.transitory_state = False
        await self.async_update_ha_state()

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return False


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Elmax switch platform."""
    coordinator: ElmaxCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    def _discover_new_devices():
        panel_status = coordinator.panel_status  # type: PanelStatus
        # In case the panel is offline, its status will be None. In that case, simply do nothing
        if panel_status is None:
            return

        # Otherwise, add all the entities we found
        entities = []
        for actuator in panel_status.actuators:
            entity = ElmaxSwitch(
                panel=coordinator.panel_entry,
                elmax_device=actuator,
                panel_version=panel_status.release,
                coordinator=coordinator,
            )
            if entity.unique_id not in known_devices:
                entities.append(entity)
        async_add_entities(entities, True)
        known_devices.update([entity.unique_id for entity in entities])

    # Register a listener for the discovery of new devices
    coordinator.async_add_listener(_discover_new_devices)

    # Immediately run a discovery, so we don't need to wait for the next update
    _discover_new_devices()
