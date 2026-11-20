"""Services for the person integration."""

from enum import StrEnum

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.service import async_register_admin_service

from .const import DATA_PERSON, DOMAIN
from .helpers import filter_yaml_data


class PersonService(StrEnum):
    """Store keys for person services."""

    RELOAD = "reload"


async def _async_reload_yaml(call: ServiceCall) -> None:
    """Reload YAML."""
    hass = call.hass
    data = hass.data[DATA_PERSON]
    conf = await data.entity_component.async_prepare_reload(skip_reset=True)
    await data.yaml_collection.async_load(
        await filter_yaml_data(hass, conf.get(DOMAIN, []))
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the person integration."""
    async_register_admin_service(hass, DOMAIN, PersonService.RELOAD, _async_reload_yaml)
