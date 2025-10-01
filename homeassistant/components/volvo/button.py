"""Volvo buttons."""

from dataclasses import dataclass
import logging

from volvocarsapi.models import VolvoApiException, VolvoCarsApiBaseModel

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import VolvoBaseCoordinator, VolvoConfigEntry
from .entity import VolvoEntity, VolvoEntityDescription

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class VolvoButtonDescription(ButtonEntityDescription, VolvoEntityDescription):
    """Describes a Volvo button entity."""

    api_command: str
    required_command_key: str


_DESCRIPTIONS: tuple[VolvoButtonDescription, ...] = (
    VolvoButtonDescription(
        key="climatization_start",
        api_command="climatization-start",
        required_command_key="CLIMATIZATION_START",
        icon="mdi:air-conditioner",
    ),
    VolvoButtonDescription(
        key="climatization_stop",
        api_command="climatization-stop",
        required_command_key="CLIMATIZATION_STOP",
        icon="mdi:air-conditioner",
    ),
    VolvoButtonDescription(
        key="flash",
        api_command="flash",
        required_command_key="FLASH",
        icon="mdi:alarm-light-outline",
    ),
    VolvoButtonDescription(
        key="honk",
        api_command="honk",
        required_command_key="HONK",
        icon="mdi:trumpet",
    ),
    VolvoButtonDescription(
        key="honk_flash",
        api_command="honk-flash",
        required_command_key="HONK_AND_FLASH",
        icon="mdi:alarm-light",
    ),
)


async def async_setup_entry(
    _: HomeAssistant,
    entry: VolvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    coordinator = entry.runtime_data.command_coordinator

    buttons = [
        VolvoCarsButton(coordinator, description)
        for description in _DESCRIPTIONS
        if description.required_command_key in coordinator.commands
    ]

    async_add_entities(buttons)


class VolvoCarsButton(VolvoEntity, ButtonEntity):
    """Volvo button."""

    entity_description: VolvoButtonDescription

    def __init__(
        self,
        coordinator: VolvoBaseCoordinator,
        description: VolvoButtonDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description)

    async def async_press(self) -> None:
        """Handle the button press."""

        try:
            _LOGGER.debug("Command %s executing", self.entity_description.api_command)

            result = await self.coordinator.context.api.async_execute_command(
                self.entity_description.api_command
            )

            status = result.invoke_status if result else ""

            _LOGGER.debug(
                "Command %s result: %s",
                self.entity_description.api_command,
                status,
            )

            if status != "COMPLETED":
                _LOGGER.warning(
                    "Command %s not successful: %s",
                    self.entity_description.api_command,
                    status,
                )
        except VolvoApiException as ex:
            _LOGGER.debug("Command %s error", self.entity_description.api_command)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_error"
            ) from ex

    def _update_state(self, api_field: VolvoCarsApiBaseModel | None) -> None:
        """Update the state of the entity."""
