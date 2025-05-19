"""Repairs for IRM KMI integration."""

import logging
from typing import Any

from irm_kmi_api import IrmKmiApiClient, IrmKmiApiError
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from . import async_reload_entry
from .const import (
    OUT_OF_BENELUX,
    REPAIR_OPT_DELETE,
    REPAIR_OPT_MOVE,
    REPAIR_OPTIONS,
    REPAIR_SOLUTION,
    USER_AGENT,
)
from .utils import modify_from_config

_LOGGER = logging.getLogger(__name__)


class OutOfBeneluxRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, data: dict) -> None:
        """Start a new repair flow when the zone is move outside of Benelux."""
        self._data: dict = data

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirmation step of a fix flow."""
        errors = {}

        config_entry = self.hass.config_entries.async_get_entry(
            self._data["config_entry_id"]
        )

        if config_entry is None:
            errors[REPAIR_SOLUTION] = "config_entry_none"

        if user_input is not None and not errors:
            if user_input[REPAIR_SOLUTION] == REPAIR_OPT_MOVE:
                if (zone := self.hass.states.get(self._data["zone"])) is None:
                    errors[REPAIR_SOLUTION] = "zone_not_exist"

                if not errors:
                    assert zone is not None  # Assert is here for mypy linting.
                    api_data = {}
                    try:
                        api_data = await IrmKmiApiClient(
                            session=async_get_clientsession(self.hass),
                            user_agent=USER_AGENT,
                        ).get_forecasts_coord(
                            {
                                "lat": zone.attributes[ATTR_LATITUDE],
                                "long": zone.attributes[ATTR_LONGITUDE],
                            }
                        )
                    except IrmKmiApiError:
                        errors[REPAIR_SOLUTION] = "api_error"
                        _LOGGER.exception(
                            "Encountered an unexpected error while checking the location with the API"
                        )

                    if api_data.get("cityName", None) in OUT_OF_BENELUX:
                        errors[REPAIR_SOLUTION] = "out_of_benelux"

                if not errors:
                    assert config_entry is not None  # Assert is here for mypy linting.
                    modify_from_config(
                        self.hass, self._data["config_entry_id"], enable=True
                    )
                    await async_reload_entry(self.hass, config_entry)

            elif user_input[REPAIR_SOLUTION] == REPAIR_OPT_DELETE:
                await self.hass.config_entries.async_remove(
                    self._data["config_entry_id"]
                )
            else:
                errors[REPAIR_SOLUTION] = "invalid_choice"

            if not errors:
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            errors=errors,
            description_placeholders={"zone": self._data["zone"]},
            data_schema=vol.Schema(
                {
                    vol.Required(
                        REPAIR_SOLUTION, default=REPAIR_OPT_MOVE
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=REPAIR_OPTIONS, translation_key=REPAIR_SOLUTION
                        )
                    ),
                }
            ),
        )


async def async_create_fix_flow(
    _hass: HomeAssistant,
    _issue_id: str,
    data: dict[Any, Any],
) -> OutOfBeneluxRepairFlow:
    """Create flow."""
    return OutOfBeneluxRepairFlow(data)
