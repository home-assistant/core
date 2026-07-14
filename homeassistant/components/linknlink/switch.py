"""Switch platform for LinknLink."""

from typing import Any, override

from aiolinknlink import UltraError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .binary_sensor import _as_bool
from .const import DOMAIN
from .coordinator import LinknLinkConfigEntry, LinknLinkCoordinator
from .entity import LinknLinkEntity

PARALLEL_UPDATES = 1

SWITCH_DESCRIPTIONS: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(key="power", translation_key="power"),
    SwitchEntityDescription(key="switch", translation_key="switch"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinknLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LinknLink switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        LinknLinkSwitch(coordinator, description, subdevice_id)
        for subdevice_id, child in coordinator.data.children.items()
        for description in SWITCH_DESCRIPTIONS
        if description.key in child.fields
    )


class LinknLinkSwitch(LinknLinkEntity, SwitchEntity):
    """Representation of a LinknLink child-device switch."""

    entity_description: SwitchEntityDescription

    def __init__(
        self,
        coordinator: LinknLinkCoordinator,
        description: SwitchEntityDescription,
        subdevice_id: str,
    ) -> None:
        """Initialize a LinknLink switch."""
        super().__init__(coordinator, description, subdevice_id)
        self._subdevice_id = subdevice_id

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the switch is on."""
        return _as_bool(self.source_value)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_state(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_state(False)

    async def _async_set_state(self, value: bool) -> None:
        """Set the switch state on the device."""
        session = self.coordinator.session
        assert session is not None
        assert self._subdevice_id is not None
        try:
            await self.coordinator.client.control(
                session,
                self.entity_description.key,
                self._subdevice_id,
                {self.entity_description.key: value},
            )
        except UltraError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="control_error",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
