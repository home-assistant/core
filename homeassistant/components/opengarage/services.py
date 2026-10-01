"""Administrative actions for OpenGarage."""

import probatio

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import service
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import DOMAIN
from .coordinator import OpenGarageConfigEntry


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Wi-Fi reset action for administrators."""

    async def async_reset_wifi(call: ServiceCall) -> None:
        """Reset a loaded device into access-point mode."""
        entry: OpenGarageConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
        )
        await entry.runtime_data.async_command(
            entry.runtime_data.open_garage_connection.ap_mode
        )

    service.async_register_admin_service(
        hass,
        DOMAIN,
        "reset_wifi",
        async_reset_wifi,
        schema=probatio.Schema(
            {
                probatio.Required(ATTR_CONFIG_ENTRY_ID): ConfigEntrySelector(
                    {"integration": DOMAIN}
                )
            }
        ),
    )
