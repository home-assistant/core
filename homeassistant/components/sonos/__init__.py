"""Support to embed Sonos."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import CONF_HOSTS
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.loader import bind_hass

from .const import DATA_SONOS, DOMAIN

CONF_ADVERTISE_ADDR = "advertise_addr"
CONF_INTERFACE_ADDR = "interface_addr"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                MP_DOMAIN: vol.Schema(
                    {
                        vol.Optional(CONF_ADVERTISE_ADDR): cv.string,
                        vol.Optional(CONF_INTERFACE_ADDR): cv.string,
                        vol.Optional(CONF_HOSTS): vol.All(
                            cv.ensure_list_csv, [cv.string]
                        ),
                    }
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Sonos component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up Sonos from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MP_DOMAIN)
    )
    return True


@bind_hass
def get_coordinator_id(hass, entity_id):
    """Obtain the unique_id of a device's coordinator.

    This function is safe to run inside the event loop.
    """
    if DATA_SONOS not in hass.data:
        raise HomeAssistantError("Sonos integration not set up")

    device = next(
        (x for x in hass.data[DATA_SONOS].entities if x.entity_id == entity_id), None
    )

    if device.is_coordinator:
        return device.unique_id
    return device.coordinator.unique_id
