"""Update support for the NEW_NAME integration."""

from homeassistant.components.update import UpdateDescription, UpdateRegistration
from homeassistant.core import HomeAssistant, callback


@callback
def async_register(registration: UpdateRegistration) -> None:
    """Register the update handler."""
    registration.async_register(get_pending_updates)


async def get_pending_updates(hass: HomeAssistant) -> list[UpdateDescription]:
    """Get pending updates."""
    # TODO: Add your logic to gather updates here.
    # And return a list of UpdateDescription objects.
    return []


async def handle_update(
    hass: HomeAssistant,
    update_details: UpdateDescription,
) -> bool:
    """Handle an update."""
    # TODO: Add your logic to perform updates here.
    # And return a bool to indicate if the update where successful or not.
    return True
