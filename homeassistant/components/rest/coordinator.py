"""RESTful Data Update Coordinator."""

from datetime import timedelta
from functools import partial
import logging
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
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

        self.rest = rest

        if resource_template or payload_template:

            async def _async_refresh_with_templates() -> None:
                if resource_template:
                    self.rest.set_url(
                        resource_template.async_render(parse_result=False)
                    )
                if payload_template:
                    self.rest.set_payload(
                        payload_template.async_render(parse_result=False)
                    )
                await self.rest.async_update(config_entry is None)

            update_method = _async_refresh_with_templates
        else:
            update_method = partial(self.rest.async_update, config_entry is None)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="rest data",
            update_interval=update_interval,
            update_method=update_method,
        )

    @override
    async def _async_update_data(self) -> None:
        try:
            await super()._async_update_data()
        except TemplateError as ex:
            ex.translation_domain = DOMAIN
            ex.translation_key = "template_error"
            ex.translation_placeholders = {"template_error_message": str(ex)}
            raise
        if (
            self.config_entry is not None
            and self.rest.data is None
            and self.rest.last_exception is not None
        ):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key=(
                    "endpoint_error"
                    if not isinstance(self.rest.last_exception, TimeoutError)
                    else "timeout_error"
                ),
                translation_placeholders={
                    "endpoint_error_message": str(self.rest.last_exception)
                },
            ) from self.rest.last_exception
