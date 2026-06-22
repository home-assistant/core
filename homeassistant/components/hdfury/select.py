"""Select platform for HDFury Integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from hdfury import OPERATION_MODES, TX0_INPUT_PORTS, TX1_INPUT_PORTS, HDFuryError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HDFuryConfigEntry
from .const import DOMAIN
from .entity import HDFuryEntity

if TYPE_CHECKING:
    from . import HDFuryRuntimeData

PARALLEL_UPDATES = 1


@dataclass(kw_only=True, frozen=True)
class HDFurySelectEntityDescription(SelectEntityDescription):
    """Description for HDFury select entities."""

    set_value_fn: Callable[[HDFuryRuntimeData, str], Awaitable[None]]


SELECT_PORTS: tuple[HDFurySelectEntityDescription, ...] = (
    HDFurySelectEntityDescription(
        key="portseltx0",
        translation_key="portseltx0",
        options=list(TX0_INPUT_PORTS.keys()),
        set_value_fn=lambda runtime_data, value: _set_ports(
            runtime_data, "portseltx0", value
        ),
    ),
    HDFurySelectEntityDescription(
        key="portseltx1",
        translation_key="portseltx1",
        options=list(TX1_INPUT_PORTS.keys()),
        set_value_fn=lambda runtime_data, value: _set_ports(
            runtime_data, "portseltx1", value
        ),
    ),
)


SELECT_OPERATION_MODE: HDFurySelectEntityDescription = HDFurySelectEntityDescription(
    key="opmode",
    translation_key="opmode",
    options=list(OPERATION_MODES.keys()),
    set_value_fn=lambda runtime_data, value: runtime_data.client.set_operation_mode(
        value
    ),
)


async def _set_ports(runtime_data: HDFuryRuntimeData, key: str, value: str) -> None:
    info = runtime_data.info_coordinator.data
    tx0 = value if key == "portseltx0" else info.get("portseltx0")
    tx1 = value if key == "portseltx1" else info.get("portseltx1")

    if tx0 is None or tx1 is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="tx_state_error",
            translation_placeholders={"details": f"tx0={tx0}, tx1={tx1}"},
        )

    await runtime_data.client.set_port_selection(tx0, tx1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HDFuryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects using the platform schema."""

    coordinator = entry.runtime_data.info_coordinator

    entities: list[HDFuryEntity] = [
        HDFurySelect(coordinator, description)
        for description in SELECT_PORTS
        if description.key in coordinator.data
    ]

    if "opmode" in coordinator.data:
        entities.append(HDFurySelect(coordinator, SELECT_OPERATION_MODE))

    async_add_entities(entities)


class HDFurySelect(HDFuryEntity, SelectEntity):
    """HDFury Select Class."""

    entity_description: HDFurySelectEntityDescription

    @property
    def current_option(self) -> str:
        """Return the current option."""

        return self.coordinator.data[self.entity_description.key]

    async def async_select_option(self, option: str) -> None:
        """Update the current option."""

        runtime_data = self.coordinator.config_entry.runtime_data

        try:
            await self.entity_description.set_value_fn(runtime_data, option)
        except HDFuryError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error

        await self.coordinator.async_request_refresh()
