"""Config flow for the School Holidays integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_COUNTRY, CONF_NAME, CONF_REGION

from .const import COUNTRIES, DOMAIN, REGIONS
from .utils import generate_unique_id


class SchoolHolidaysConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for School Holidays."""

    VERSION = 1
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._name: str = ""
        self._country: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Enter calendar name and select country."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get(CONF_NAME, "").strip()
            if not name:
                errors[CONF_NAME] = "required"

            country = user_input.get(CONF_COUNTRY)
            if not country:
                errors[CONF_COUNTRY] = "required"

            if not errors:
                self._name = str(name)
                self._country = str(country)
                return await self.async_step_region()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_COUNTRY): vol.In(COUNTRIES),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            description_placeholders={},
            errors=errors,
        )

    async def async_step_region(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select region for the selected country."""
        errors: dict[str, str] = {}
        regions = REGIONS.get(self._country, [])

        if user_input is not None:
            region = user_input.get(CONF_REGION)
            if not region:
                errors[CONF_REGION] = "required"
            else:
                # Perform case-insensitive region matching.
                region_lower = region.lower()
                matched_region = None
                for valid_region in regions:
                    if valid_region.lower() == region_lower:
                        matched_region = valid_region
                        break

                if matched_region is None:
                    errors[CONF_REGION] = "invalid"
                else:
                    region = matched_region

            if not errors:
                # Assert that region is a string for type safety.
                if TYPE_CHECKING:
                    assert isinstance(region, str)
                await self.async_set_unique_id(
                    generate_unique_id(self._country, region)
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._name,
                    data={
                        CONF_NAME: self._name,
                        CONF_COUNTRY: self._country,
                        CONF_REGION: region,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_REGION): vol.In(regions),
            }
        )

        return self.async_show_form(
            step_id="region",
            data_schema=data_schema,
            description_placeholders={},
            errors=errors,
        )
