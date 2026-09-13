"""Support for Denon AVR Audyssey switch entities."""

import logging

from denonavr import DenonAVR
from denonavr.const import MAIN_ZONE
from denonavr.exceptions import DenonAvrError

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DenonavrConfigEntry
from .const import CONF_SERIAL_NUMBER, DOMAIN
from .entity import DenonAvrPendingValueEntity

_LOGGER = logging.getLogger(__name__)

# See the matching constant in select.py.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DenonavrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DenonAVR switch entities from a config entry."""
    receiver = config_entry.runtime_data

    # Dynamic EQ, like the other Audyssey settings, applies to the whole
    # receiver rather than per zone.
    main_receiver = receiver.zones[MAIN_ZONE]

    if config_entry.data.get(CONF_SERIAL_NUMBER) is not None:
        unique_id_base = config_entry.unique_id
    else:
        unique_id_base = config_entry.entry_id

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.unique_id or config_entry.entry_id)},
    )

    # See the matching comment in select.py.
    try:
        await main_receiver.async_update_audyssey()
    except DenonAvrError as err:
        _LOGGER.debug(
            "Could not fetch initial Audyssey status for %s: %s",
            main_receiver.name,
            err,
        )

    async_add_entities(
        [DenonAvrDynamicEqSwitch(main_receiver, unique_id_base, device_info)]
    )


class DenonAvrDynamicEqSwitch(DenonAvrPendingValueEntity[bool], SwitchEntity):
    """Representation of the Denon AVR Dynamic EQ switch."""

    _attr_translation_key = "dynamic_eq"
    _attr_name = "Dynamic EQ"
    _attr_icon = "mdi:auto-fix"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        receiver: DenonAVR,
        unique_id_base: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the switch."""
        super().__init__(receiver, f"{unique_id_base}-dynamic_eq", device_info)

    def _read_value(self) -> bool | None:
        """Return the receiver's own confirmed Dynamic EQ state."""
        return self._receiver.dynamic_eq

    @property
    def available(self) -> bool:
        """Return True if the receiver reports a Dynamic EQ state."""
        return self._current_value is not None

    @property
    def is_on(self) -> bool | None:
        """Return True if Dynamic EQ is on."""
        return self._current_value

    async def async_turn_on(self, **kwargs) -> None:
        """Turn Dynamic EQ on."""
        await self._async_set_dynamic_eq(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn Dynamic EQ off."""
        await self._async_set_dynamic_eq(False)

    async def _async_set_dynamic_eq(self, dynamic_eq: bool) -> None:
        """Set Dynamic EQ and refresh Audyssey values that depend on it.

        Reference Level Offset can only be set while Dynamic EQ is on,
        so flipping this switch changes that entity's availability too
        once the refresh completes.
        """
        await self._async_apply_change(
            send=(
                self._receiver.async_dynamic_eq_on
                if dynamic_eq
                else self._receiver.async_dynamic_eq_off
            ),
            refresh=self._receiver.async_update_audyssey,
            value=dynamic_eq,
            error_label="Dynamic EQ",
        )
