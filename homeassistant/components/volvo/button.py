"""Volvo buttons."""

from dataclasses import dataclass
import logging

from volvocarsapi.models import VolvoApiException

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import VolvoConfigEntry
from .entity import VolvoBaseEntity, VolvoEntityDescription

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class VolvoButtonDescription(VolvoEntityDescription, ButtonEntityDescription):
    """Describes a Volvo button entity."""

    api_command: str
    required_command_key: str
    data: dict[str, int] | None = None


_DESCRIPTIONS: tuple[VolvoButtonDescription, ...] = (
    VolvoButtonDescription(
        key="climatization_start",
        api_command="climatization-start",
        required_command_key="CLIMATIZATION_START",
    ),
    VolvoButtonDescription(
        key="climatization_stop",
        api_command="climatization-stop",
        required_command_key="CLIMATIZATION_STOP",
    ),
    VolvoButtonDescription(
        key="engine_start",
        api_command="engine-start",
        required_command_key="ENGINE_START",
        data={"runtimeMinutes": 15},
    ),
    VolvoButtonDescription(
        key="engine_stop",
        api_command="engine-stop",
        required_command_key="ENGINE_STOP",
    ),
    VolvoButtonDescription(
        key="flash",
        api_command="flash",
        required_command_key="FLASH",
    ),
    VolvoButtonDescription(
        key="honk",
        api_command="honk",
        required_command_key="HONK",
    ),
    VolvoButtonDescription(
        key="honk_flash",
        api_command="honk-flash",
        required_command_key="HONK_AND_FLASH",
    ),
    VolvoButtonDescription(
        key="lock_reduced_guard",
        api_command="lock-reduced-guard",
        required_command_key="LOCK_REDUCED_GUARD",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VolvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    async_add_entities(
        [
            VolvoButton(entry, description)
            for description in _DESCRIPTIONS
            if description.required_command_key
            in entry.runtime_data.context.supported_commands
        ]
    )


class VolvoButton(VolvoBaseEntity, ButtonEntity):
    """Volvo button."""

    entity_description: VolvoButtonDescription

    async def async_press(self) -> None:
        """Handle the button press."""

        command = self.entity_description.api_command
        _LOGGER.debug("Command %s executing", command)

        try:
            result = await self.entry.runtime_data.context.api.async_execute_command(
                self.entity_description.api_command, self.entity_description.data
            )
        except VolvoApiException as ex:
            _LOGGER.debug("Command '%s' error", command)
            self._raise(command, message=ex.message, exception=ex)

        status = result.invoke_status if result else ""

        if status != "COMPLETED":
            self._raise(
                command, status=status, message=result.message if result else ""
            )

    def _raise(
        self,
        command: str,
        *,
        status: str = "",
        message: str = "",
        exception: Exception | None = None,
    ) -> None:
        error = HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failure",
            translation_placeholders={
                "command": command,
                "status": status,
                "message": message,
            },
        )

        if exception:
            raise error from exception

        raise error
