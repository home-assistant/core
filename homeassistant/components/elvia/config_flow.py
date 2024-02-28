"""Config flow for Elvia integration."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from elvia import Elvia, error as ElviaError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.util import dt as dt_util

from .const import CONF_METERING_POINT_ID, DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elvia."""

    def __init__(self) -> None:
        """Initialize."""
        self._api_token: str | None = None
        self._metering_point_ids: list[str] | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._api_token = api_token = user_input[CONF_API_TOKEN]
            client = Elvia(meter_value_token=api_token).meter_value()
            try:
                end_time = dt_util.utcnow()
                results = await client.get_meter_values(
                    start_time=(end_time - timedelta(hours=1)).isoformat(),
                    end_time=end_time.isoformat(),
                )

            except ElviaError.AuthError as exception:
                LOGGER.error("Authentication error %s", exception)
                errors["base"] = "invalid_auth"
            except ElviaError.ElviaException as exception:
                LOGGER.error("Unknown error %s", exception)
                errors["base"] = "unknown"
            else:
                try:
                    self._metering_point_ids = metering_point_ids = [
                        x["meteringPointId"] for x in results["meteringpoints"]
                    ]
                except KeyError:
                    return self.async_abort(reason="no_metering_points")

                if (meter_count := len(metering_point_ids)) > 1:
                    return await self.async_step_select_meter()
                if meter_count == 1:
                    return await self._create_config_entry(
                        api_token=api_token,
                        metering_point_id=metering_point_ids[0],
                    )

                return self.async_abort(reason="no_metering_points")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_select_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle selecting a metering point ID."""
        if TYPE_CHECKING:
            assert self._metering_point_ids is not None
            assert self._api_token is not None

        if user_input is not None:
            return await self._create_config_entry(
                api_token=self._api_token,
                metering_point_id=user_input[CONF_METERING_POINT_ID],
            )

        return self.async_show_form(
            step_id="select_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_METERING_POINT_ID,
                        default=self._metering_point_ids[0],
                    ): vol.In(self._metering_point_ids),
                }
            ),
        )

    async def _create_config_entry(
        self,
        api_token: str,
        metering_point_id: str,
    ) -> FlowResult:
        """Store metering point ID and API token."""
        if (await self.async_set_unique_id(metering_point_id)) is not None:
            return self.async_abort(
                reason="metering_point_id_already_configured",
                description_placeholders={"metering_point_id": metering_point_id},
            )
        return self.async_create_entry(
            title=metering_point_id,
            data={
                CONF_API_TOKEN: api_token,
                CONF_METERING_POINT_ID: metering_point_id,
            },
        )
