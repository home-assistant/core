"""Select platform for HDFury Integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from hdfury import OPERATION_MODES, TX0_INPUT_PORTS, TX1_INPUT_PORTS, HDFuryError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import HDFuryConfigEntry, HDFuryCoordinator
from .entity import HDFuryEntity

PARALLEL_UPDATES = 1


@dataclass(kw_only=True, frozen=True)
class HDFurySelectEntityDescription(SelectEntityDescription):
    """Description for HDFury select entities."""

    set_value_fn: Callable[[HDFuryCoordinator, str], Awaitable[None]]


SELECT_PORTS: tuple[HDFurySelectEntityDescription, ...] = (
    HDFurySelectEntityDescription(
        key="portseltx0",
        translation_key="portseltx0",
        options=list(TX0_INPUT_PORTS.keys()),
        set_value_fn=lambda coordinator, value: _set_ports(coordinator),
    ),
    HDFurySelectEntityDescription(
        key="portseltx1",
        translation_key="portseltx1",
        options=list(TX1_INPUT_PORTS.keys()),
        set_value_fn=lambda coordinator, value: _set_ports(coordinator),
    ),
)


SELECT_OPERATION_MODE: HDFurySelectEntityDescription = HDFurySelectEntityDescription(
    key="opmode",
    translation_key="opmode",
    options=list(OPERATION_MODES.keys()),
    set_value_fn=lambda coordinator, value: coordinator.client.set_operation_mode(
        value
    ),
)


async def _set_ports(coordinator: HDFuryCoordinator) -> None:
    tx0 = coordinator.data.info.get("portseltx0")
    tx1 = coordinator.data.info.get("portseltx1")

    if tx0 is None or tx1 is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="tx_state_error",
            translation_placeholders={"details": f"tx0={tx0}, tx1={tx1}"},
        )

    await coordinator.client.set_port_selection(tx0, tx1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HDFuryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects using the platform schema."""

    coordinator = entry.runtime_data

    entities: list[HDFuryEntity] = [
        HDFurySelect(coordinator, description)
        for description in SELECT_PORTS
        if description.key in coordinator.data.info
    ]

    # Add OPMODE select if present
    if "opmode" in coordinator.data.info:
        entities.append(HDFurySelect(coordinator, SELECT_OPERATION_MODE))

    async_add_entities(entities)


class HDFurySelect(HDFuryEntity, SelectEntity):
    """HDFury Select Class."""

    entity_description: HDFurySelectEntityDescription

    @property
    def current_option(self) -> str:
        """Return the current option."""

        return self.coordinator.data.info[self.entity_description.key]

    async def async_select_option(self, option: str) -> None:
        """Update the current option."""

        # Update local data first
        self.coordinator.data.info[self.entity_description.key] = option

        # Send command to device
        try:
            await self.entity_description.set_value_fn(self.coordinator, option)
        except HDFuryError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error

        # Trigger HA coordinator refresh
        await self.coordinator.async_request_refresh()
