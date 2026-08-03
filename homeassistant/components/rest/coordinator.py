"""RESTful Data Update Coordinator."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .data import RestData

_LOGGER = logging.getLogger(__name__)

RestConfigEntry = ConfigEntry["RestCoordinator"]


class RestCoordinator(DataUpdateCoordinator[None]):
    """Rest coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        rest: RestData,
        config_entry: RestConfigEntry | None,
        resource_template: template.Template | None,
        payload_template: template.Template | None,
        update_interval: timedelta,
    ) -> None:
        """Initialize a data update coordinator."""

        self.rest: RestData = rest

        if resource_template or payload_template:

            async def _async_refresh_with_templates() -> None:
                if resource_template:
                    rest.set_url(resource_template.async_render(parse_result=False))
                if payload_template:
                    rest.set_payload(payload_template.async_render(parse_result=False))
                await rest.async_update()

            update_method = _async_refresh_with_templates
        else:
            update_method = rest.async_update

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="rest data",
            update_interval=update_interval,
            update_method=update_method,
        )
