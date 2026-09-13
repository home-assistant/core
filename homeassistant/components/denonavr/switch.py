"""Support for Denon AVR Audyssey switch entities."""

from typing import Any, cast, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DenonavrConfigEntry
from .const import CONF_SERIAL_NUMBER, DOMAIN
from .coordinator import DenonAvrDataUpdateCoordinator
from .entity import DenonAvrPendingValueEntity

# See the matching constant in select.py.
PARALLEL_UPDATES = 1

# Gives this a fallback name (via entity_description.name, checked
# after translation_key in Entity._name_internal) if translation
# lookup ever fails to load - e.g. a custom_components install missing
# translations/en.json, which silently leaves the entity nameless
# otherwise. Not _attr_name: that's checked *before* translation_key,
# so it would permanently block translations rather than just back
# them up (this is exactly the bug that class attribute caused here
# previously).
DYNAMIC_EQ_DESCRIPTION = SwitchEntityDescription(
    key="dynamic_eq",
    translation_key="dynamic_eq",
    name="Dynamic EQ",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DenonavrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DenonAVR switch entities from a config entry."""
    data = config_entry.runtime_data

    if (
        config_entry.data.get(CONF_SERIAL_NUMBER) is not None
        and config_entry.unique_id is not None
    ):
        unique_id_base = config_entry.unique_id
    else:
        unique_id_base = config_entry.entry_id

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.unique_id or config_entry.entry_id)},
    )

    async_add_entities(
        [
            DenonAvrDynamicEqSwitch(
                data.audyssey_coordinator, unique_id_base, device_info
            )
        ]
    )


class DenonAvrDynamicEqSwitch(DenonAvrPendingValueEntity[bool], SwitchEntity):
    """Representation of the Denon AVR Dynamic EQ switch."""

    entity_description: SwitchEntityDescription

    def __init__(
        self,
        coordinator: DenonAvrDataUpdateCoordinator,
        unique_id_base: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, f"{unique_id_base}-dynamic_eq", device_info)
        self.entity_description = DYNAMIC_EQ_DESCRIPTION

    @override
    def _read_value(self) -> bool | None:
        """Return the receiver's own confirmed Dynamic EQ state."""
        # denonavr ships no py.typed marker, so its attributes are
        # untyped (Any) to mypy - cast to what this actually returns.
        return cast("bool | None", self._receiver.dynamic_eq)

    @property
    @override
    def available(self) -> bool:
        """Return True if the receiver reports a Dynamic EQ state.

        Also False whenever this entity's coordinator's last refresh
        failed - see the matching comment on DenonAvrSelect.
        """
        return super().available and self._current_value is not None

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if Dynamic EQ is on."""
        return self._current_value

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn Dynamic EQ on."""
        await self._async_set_dynamic_eq(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn Dynamic EQ off."""
        await self._async_set_dynamic_eq(False)

    async def _async_set_dynamic_eq(self, dynamic_eq: bool) -> None:
        """Set Dynamic EQ.

        Reference Level Offset can only be set while Dynamic EQ is on,
        so flipping this switch changes that entity's availability too
        once the shared coordinator refresh completes.
        """
        await self._async_apply_change(
            send=(
                self._receiver.async_dynamic_eq_on
                if dynamic_eq
                else self._receiver.async_dynamic_eq_off
            ),
            value=dynamic_eq,
            error_label="Dynamic EQ",
        )
