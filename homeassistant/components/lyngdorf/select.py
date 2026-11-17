"""Select platform for Lyngdorf integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from lyngdorf import LyngdorfInvalidValueError, LyngdorfReceiver, Selector

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import LyngdorfEntity
from .models import LyngdorfConfigEntry

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LyngdorfSelectEntityDescription(SelectEntityDescription):
    """Describe a Lyngdorf select entity."""

    selector_fn: Callable[[LyngdorfReceiver], Selector | None]


SELECT_ENTITIES: tuple[LyngdorfSelectEntityDescription, ...] = (
    LyngdorfSelectEntityDescription(
        key="room_perfect_position",
        translation_key="room_perfect_position",
        selector_fn=lambda r: r.room_perfect_position_selector,
    ),
    LyngdorfSelectEntityDescription(
        key="voicing",
        translation_key="voicing",
        selector_fn=lambda r: r.voicing_selector,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lyngdorf select entities from a config entry."""
    runtime_data = config_entry.runtime_data

    async_add_entities(
        LyngdorfSelect(
            runtime_data.receiver, config_entry, runtime_data.device_info, description
        )
        for description in SELECT_ENTITIES
        if description.selector_fn(runtime_data.receiver) is not None
    )


class LyngdorfSelect(LyngdorfEntity, SelectEntity):
    """Lyngdorf select entity."""

    entity_description: LyngdorfSelectEntityDescription

    def __init__(
        self,
        receiver: LyngdorfReceiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
        description: LyngdorfSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(receiver, device_info)
        if TYPE_CHECKING:
            assert config_entry.unique_id
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"

    @property
    def _selector(self) -> Selector:
        selector = self.entity_description.selector_fn(self._receiver)
        if TYPE_CHECKING:
            assert selector is not None
        return selector

    @override
    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self._selector.value

    @override
    @property
    def options(self) -> list[str]:
        """Return available options."""
        return self._selector.options

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""
        try:
            await self._selector.select(option)
        except LyngdorfInvalidValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_option",
                translation_placeholders={
                    "option": option,
                    "options": ", ".join(self.options),
                },
            ) from err
