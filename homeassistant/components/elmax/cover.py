"""Elmax cover platform."""
from typing import Optional

from elmax_api.model.command import CoverCommand
from elmax_api.model.cover_status import CoverStatus
from elmax_api.model.endpoint import DeviceEndpoint
from elmax_api.model.panel import PanelEntry, PanelStatus

from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.components.elmax import ElmaxCoordinator, ElmaxEntity
from homeassistant.components.elmax.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType


class ElmaxCover(ElmaxEntity, CoverEntity):
    """Implement the Elmax cover entity."""

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
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return False

    @property
    def is_closed(self) -> Optional[bool]:
        """Return if the cover is closed or not."""
        return self._device.position == 0

    @property
    def current_cover_position(self) -> Optional[int]:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._device.position

    @property
    def is_opening(self) -> Optional[bool]:
        """Return if the cover is opening or not."""
        state = self._device.status
        if self.transitory_state is not None:
            state = self.transitory_state

        return state == CoverStatus.UP

    @property
    def is_closing(self) -> Optional[bool]:
        """Return if the cover is closing or not."""
        state = self._device.status
        if self.transitory_state is not None:
            state = self.transitory_state

        return state == CoverStatus.DOWN

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        # To stop the cover, Elmax requires us to re-issue the same command once again.
        if self.transitory_state is not None:
            if self.transitory_state == CoverStatus.UP:
                command = CoverCommand.UP
            elif self.transitory_state == CoverStatus.DOWN:
                command = CoverCommand.DOWN
            else:
                return

            client = self._coordinator.http_client
            await client.execute_command(
                endpoint_id=self._device.endpoint_id, command=command
            )
            self.transitory_state = CoverStatus.IDLE

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        client = self._coordinator.http_client
        await client.execute_command(
            endpoint_id=self._device.endpoint_id, command=CoverCommand.UP
        )
        self.transitory_state = CoverStatus.UP

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        client = self._coordinator.http_client
        await client.execute_command(
            endpoint_id=self._device.endpoint_id, command=CoverCommand.DOWN
        )
        self.transitory_state = CoverStatus.DOWN


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
    """Set up the Elmax cover platform."""
    coordinator: ElmaxCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    def _discover_new_devices():
        panel_status = coordinator.panel_status  # type: PanelStatus
        # In case the panel is offline, its status will be None. In that case, simply do nothing
        if panel_status is None:
            return

        # Otherwise, add all the entities we found
        entities = []
        for actuator in panel_status.covers:
            e = ElmaxCover(
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
