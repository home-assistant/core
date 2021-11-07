"""Elmax switch platform."""
from typing import Any

from elmax_api.model.command import SwitchCommand
from elmax_api.model.endpoint import DeviceEndpoint
from elmax_api.model.panel import PanelEntry, PanelStatus

from homeassistant.components.elmax import ElmaxCoordinator, ElmaxEntity
from homeassistant.components.elmax.const import DOMAIN
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType


class ElmaxSwitch(ElmaxEntity, SwitchEntity):
    """Implement the Elmax switch entity."""

    def __init__(
        self,
        panel: PanelEntry,
        elmax_device: DeviceEndpoint,
        panel_version: str,
        coordinator: ElmaxCoordinator,
    ):
        """Construct the object."""
        super().__init__(panel, elmax_device, panel_version, coordinator)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self._transitory_state is not None:
            return self._transitory_state
        return self._device.opened

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        client = self._coordinator.http_client
        await client.execute_command(
            endpoint_id=self._device.endpoint_id, command=SwitchCommand.TURN_ON
        )
        self.transitory_state = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        client = self._coordinator.http_client
        await client.execute_command(
            endpoint_id=self._device.endpoint_id, command=SwitchCommand.TURN_OFF
        )
        self.transitory_state = False

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return False


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
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
            e = ElmaxSwitch(
                panel=coordinator.panel_entry,
                elmax_device=actuator,
                panel_version=panel_status.release,
                coordinator=coordinator,
            )
            if e.unique_id not in known_devices:
                entities.append(e)
        async_add_entities(entities, True)
        known_devices.update([e.unique_id for e in entities])

    # Register a listener for the discovery of new devices
    coordinator.async_add_listener(_discover_new_devices)

    # Immediately run a discovery, so we don't need to wait for the next update
    _discover_new_devices()
