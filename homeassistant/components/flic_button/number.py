"""Number platform for the Flic Button integration."""

from dataclasses import dataclass
import logging
from typing import Any, override

from bleak import BleakError
from pyflic_ble import FlicProtocolError, FlicState, PushTwistMode
from pyflic_ble.const import TWIST_MODE_SLOT_CHANGING

from homeassistant.components.number import (
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlicButtonConfigEntry, FlicButtonData
from .const import CONF_PUSH_TWIST_MODE, DOMAIN
from .entity import FlicButtonEntity

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class FlicTwistNumberEntityDescription(NumberEntityDescription):
    """Describes a Flic Twist number entity."""

    mode_index: int


SLOT_DESCRIPTIONS: tuple[FlicTwistNumberEntityDescription, ...] = tuple(
    FlicTwistNumberEntityDescription(
        key=f"slot_{index + 1}",
        translation_key="slot",
        translation_placeholders={"slot_number": str(index + 1)},
        mode_index=index,
    )
    for index in range(TWIST_MODE_SLOT_CHANGING)
)

POSITION_DESCRIPTIONS: tuple[FlicTwistNumberEntityDescription, ...] = (
    FlicTwistNumberEntityDescription(
        key="twist_position",
        translation_key="twist_position",
        mode_index=0,
    ),
    FlicTwistNumberEntityDescription(
        key="push_twist_position",
        translation_key="push_twist_position",
        mode_index=TWIST_MODE_SLOT_CHANGING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlicButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flic Button number entities."""
    data = entry.runtime_data
    if not data.client.capabilities.has_selector:
        return

    push_twist_mode = PushTwistMode(
        entry.options.get(CONF_PUSH_TWIST_MODE, PushTwistMode.DEFAULT)
    )
    descriptions = (
        SLOT_DESCRIPTIONS
        if push_twist_mode is PushTwistMode.SELECTOR
        else POSITION_DESCRIPTIONS
    )

    async_add_entities(
        FlicTwistNumberEntity(data, description) for description in descriptions
    )


class FlicTwistNumberEntity(FlicButtonEntity, RestoreNumber):
    """Representation of the rotation position of a single Flic Twist mode."""

    entity_description: FlicTwistNumberEntityDescription

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_native_value: float = 0
    _pending_restore: float | None = None

    def __init__(
        self, data: FlicButtonData, description: FlicTwistNumberEntityDescription
    ) -> None:
        """Initialize the number entity."""
        super().__init__(data)
        self.entity_description = description
        self._attr_unique_id = f"{self._client.address}-{description.key}"

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last position and subscribe to rotation events."""
        await super().async_added_to_hass()

        # The device takes its rotation position from the host, and the library
        # only carries it for the lifetime of a connection, so a restart has to
        # hand it back. The button is usually still out of range at this point,
        # so the write waits for the session to come up.
        if (
            last_data := await self.async_get_last_number_data()
        ) is not None and last_data.native_value:
            self._attr_native_value = last_data.native_value
            self._pending_restore = last_data.native_value
            if self._client.state.connected:
                await self._async_restore_position()

        self.async_on_remove(
            self._client.register_rotate_event_callback(self._handle_rotate_event)
        )

    @callback
    @override
    def _handle_state_update(self, state: FlicState) -> None:
        """Hand the restored position back once the session is established."""
        super()._handle_state_update(state)

        if state.connected and self._pending_restore is not None:
            self.hass.async_create_task(
                self._async_restore_position(), eager_start=False
            )

    async def _async_restore_position(self) -> None:
        """Write the restored position to the device, once."""
        value, self._pending_restore = self._pending_restore, None
        if value is None:
            return

        try:
            await self._async_send_position(value)
        except HomeAssistantError as err:
            _LOGGER.debug("Could not restore %s: %s", self.entity_id, err)

    @callback
    def _handle_rotate_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle a rotation event for this mode."""
        if event_data["twist_mode_index"] != self.entity_description.mode_index:
            return

        self._attr_native_value = round(event_data["mode_percentage"])
        self.async_write_ha_state()

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the position of this mode on the device."""
        await self._async_send_position(value)
        self._attr_native_value = value
        self.async_write_ha_state()

    async def _async_send_position(self, value: float) -> None:
        """Send a rotation position to the device."""
        try:
            await self._client.async_send_update_twist_position(
                self.entity_description.mode_index, value
            )
        except (TimeoutError, BleakError, FlicProtocolError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_position_failed",
                translation_placeholders={"address": self._client.address},
            ) from err
