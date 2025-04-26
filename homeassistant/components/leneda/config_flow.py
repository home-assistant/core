"""Config flow for Leneda integration."""

from __future__ import annotations

from asyncio import Task
from collections.abc import Mapping
from datetime import datetime, timedelta
import logging
from typing import Any, Final

from leneda import LenedaClient
from leneda.exceptions import ForbiddenException, UnauthorizedException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_API_TOKEN,
    CONF_ENERGY_ID,
    CONF_METERING_POINTS,
    DOMAIN,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)

# Setup types
SETUP_TYPE_PROBE: Final = "probe"
SETUP_TYPE_MANUAL: Final = "manual"

# Error messages
ERROR_INVALID_METERING_POINT: Final = "invalid_metering_point"
ERROR_SELECT_AT_LEAST_ONE: Final = "select_at_least_one"
ERROR_UNKNOWN: Final = "unknown"
ERROR_EXISTING_CONFIG_NOT_FOUND: Final = "existing_config_not_found"
ERROR_UPDATED_EXISTING: Final = "updated_existing"
ERROR_DUPLICATE_METERING_POINT: Final = "duplicate_metering_point"
ERROR_FORBIDDEN: Final = "forbidden"
ERROR_UNAUTHORIZED: Final = "unauthorized"
ERROR_NO_OBIS_CODES: Final = "no_obis_codes"


class LenedaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Leneda."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._existing_entries: list[dict[str, Any]] = []
        self._use_existing: bool = False
        self._selected_energy_id: str = ""
        self._api_token: str = ""
        self._metering_points: list[str] = []
        self._current_metering_point: str = ""
        self._selected_sensors: dict[str, list[str]] = {}
        self._probing_task: Task | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> LenedaOptionsFlow:
        """Get the options flow for this handler."""
        return LenedaOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Get existing entries
        self._existing_entries = []
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            self._existing_entries.append(
                {
                    "entry_id": entry.entry_id,
                    "energy_id": entry.data.get(CONF_ENERGY_ID, ""),
                    "api_token": entry.data.get(CONF_API_TOKEN, ""),
                    "title": entry.title,
                }
            )

        # If there are no existing entries, go directly to new credentials
        if not self._existing_entries:
            return await self.async_step_new_credentials()

        # Show menu with options
        return self.async_show_menu(
            step_id="user",
            menu_options=["new_credentials", "select_existing"],
        )

    async def async_step_select_existing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle selecting an existing configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Mark that we are adding to an existing entry
            self._use_existing = True
            self._selected_energy_id = user_input["existing_energy_id"]
            # Get the API token from the existing entry
            for entry in self._existing_entries:
                if entry["energy_id"] == self._selected_energy_id:
                    self._api_token = entry["api_token"]
                    break
            return await self.async_step_add_metering_point()

        # Create options for existing energy IDs
        energy_id_options = {
            entry["energy_id"]: f"{entry['energy_id']}"
            for entry in self._existing_entries
        }

        return self.async_show_form(
            step_id="select_existing",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "existing_energy_id",
                        description="config.step.select_existing.data.existing_energy_id",
                    ): vol.In(energy_id_options)
                }
            ),
            errors=errors,
        )

    async def async_step_new_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle entering new credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Defer credential validation until a real metering point is entered
            await self.async_set_unique_id(user_input[CONF_ENERGY_ID])
            self._abort_if_unique_id_configured()
            self._selected_energy_id = user_input[CONF_ENERGY_ID]
            self._api_token = user_input[CONF_API_TOKEN]
            return await self.async_step_add_metering_point()

        return self.async_show_form(
            step_id="new_credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_TOKEN,
                        description="config.step.new_credentials.data.api_token",
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                            autocomplete="leneda-api-token",
                        )
                    ),
                    vol.Required(
                        CONF_ENERGY_ID,
                        description="config.step.new_credentials.data.energy_id",
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            autocomplete="leneda-energy-id",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_add_metering_point(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding a single metering point."""
        errors: dict[str, str] = {}

        if user_input is not None:
            metering_point = user_input["metering_point"].strip()

            if not metering_point:
                errors["base"] = ERROR_INVALID_METERING_POINT
            else:
                # Prevent adding a metering point already configured under a different Leneda energy ID
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if entry.data.get(
                        CONF_ENERGY_ID
                    ) != self._selected_energy_id and metering_point in entry.data.get(
                        CONF_METERING_POINTS, []
                    ):
                        _LOGGER.error(
                            "Metering point %s already configured for energy ID %s",
                            metering_point,
                            entry.data.get(CONF_ENERGY_ID),
                        )
                        errors["base"] = ERROR_DUPLICATE_METERING_POINT
                        break
                if not errors:
                    self._current_metering_point = metering_point
                    return await self.async_step_setup_type()

        return self.async_show_form(
            step_id="add_metering_point",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "metering_point",
                        description="config.step.metering_points.data.metering_point",
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            autocomplete="leneda-metering-point",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_setup_type(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let user choose between probing and manual setup."""
        return self.async_show_menu(
            step_id="setup_type",
            menu_options=[SETUP_TYPE_PROBE, SETUP_TYPE_MANUAL],
            description_placeholders={"metering_point": self._current_metering_point},
        )

    async def async_step_probe(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Probe the metering point for supported OBIS codes."""
        _LOGGER.debug(
            "Starting probe for metering point %s", self._current_metering_point
        )

        if not self._probing_task:
            _LOGGER.debug("Creating new probing task")
            self._probing_task = self.hass.async_create_task(self._fetch_obis_codes())

        if not self._probing_task.done():
            _LOGGER.debug("Probing task still in progress")
            return self.async_show_progress(
                progress_action="fetch_obis",
                progress_task=self._probing_task,
            )

        # Task completed — now handle result or exception
        try:
            supported_obis_codes = await self._probing_task
            self._probing_task = None
            _LOGGER.debug(
                "Probing completed, found %d OBIS codes", len(supported_obis_codes)
            )

            if not supported_obis_codes:
                _LOGGER.debug("No OBIS codes found, proceeding to manual setup")
                return self.async_show_progress_done(next_step_id="probe_no_sensors")

            # Convert OBIS codes to sensor types
            detected_sensors = []
            for obis_code in supported_obis_codes:
                for sensor_type, cfg in SENSOR_TYPES.items():
                    if cfg["obis_code"] == obis_code:
                        detected_sensors.append(sensor_type)
                        break

            _LOGGER.debug(
                "Detected %d sensors: %s", len(detected_sensors), detected_sensors
            )

            # Store detected sensors and proceed to manual setup with pre-selection
            self._selected_sensors[self._current_metering_point] = detected_sensors
            return self.async_show_progress_done(next_step_id="manual")

        except UnauthorizedException:
            _LOGGER.exception("Unauthorized while probing metering point")
            self._probing_task = None
            return self.async_abort(reason=ERROR_UNAUTHORIZED)
        except ForbiddenException:
            _LOGGER.exception("Forbidden while probing metering point")
            self._probing_task = None
            return self.async_abort(reason=ERROR_FORBIDDEN)
        except Exception:
            _LOGGER.exception("Unknown error while probing metering point")
            self._probing_task = None
            return self.async_abort(reason=ERROR_UNKNOWN)

    async def async_step_probe_no_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show menu when no sensors are detected."""
        return self.async_show_menu(
            step_id="probe_no_sensors",
            menu_options=["manual"],
            description_placeholders={
                "metering_point": self._current_metering_point,
            },
        )

    async def _fetch_obis_codes(self) -> list[str]:
        """Fetch supported OBIS codes for the current metering point."""
        _LOGGER.debug(
            "Fetching OBIS codes for metering point %s (energy_id: %s)",
            self._current_metering_point,
            self._selected_energy_id,
        )
        client = LenedaClient(
            api_key=self._api_token,
            energy_id=self._selected_energy_id,
        )

        return await self.hass.async_add_executor_job(
            client.get_supported_obis_codes, self._current_metering_point
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual sensor setup with all OBIS codes."""
        if user_input is not None:
            try:
                selected_sensors = user_input.get("sensors", [])
                if not selected_sensors:
                    return self.async_show_form(
                        step_id="manual",
                        data_schema=self._get_manual_schema(),
                        description_placeholders={
                            "metering_point": self._current_metering_point,
                            "probed_text": "",
                        },
                        errors={"base": ERROR_SELECT_AT_LEAST_ONE},
                    )

                self._selected_sensors[self._current_metering_point] = selected_sensors
                self._metering_points.append(self._current_metering_point)
                return await self.async_step_metering_points_summary()
            except Exception:
                _LOGGER.exception("Error in manual setup")
                return self.async_abort(reason=ERROR_UNKNOWN)

        # Get pre-selected sensors from probing if available
        default_sensors = self._selected_sensors.get(self._current_metering_point, [])

        return self.async_show_form(
            step_id="manual",
            data_schema=self._get_manual_schema(default_sensors),
            description_placeholders={
                "metering_point": self._current_metering_point,
                "probed_text": " (pre-selected based on probing)"
                if default_sensors
                else "",
            },
        )

    def _get_manual_schema(
        self, default_sensors: list[str] | None = None
    ) -> vol.Schema:
        """Get the schema for manual setup."""
        return vol.Schema(
            {
                vol.Required(
                    "sensors",
                    default=default_sensors or [],
                    description="config.step.manual.data.sensors",
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(SENSOR_TYPES.keys()),
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="sensors",
                    )
                ),
            }
        )

    async def async_step_metering_points_summary(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show summary of added metering points and options to add more or finish."""
        return self.async_show_menu(
            step_id="metering_points_summary",
            menu_options=["add_metering_point", "finish"],
            description_placeholders={
                "summary": "\n".join(
                    f"- {mp}:\n  {len(self._selected_sensors[mp])} sensors"
                    for mp in self._metering_points
                )
            },
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle finishing the metering points configuration."""
        try:
            if self._use_existing:
                # Get the existing entry
                existing_entry = None
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if entry.data.get(CONF_ENERGY_ID) == self._selected_energy_id:
                        existing_entry = entry
                        break

                if not existing_entry:
                    return self.async_abort(reason=ERROR_EXISTING_CONFIG_NOT_FOUND)

                # Merge existing and new metering points
                existing_metering_points = existing_entry.data.get(
                    CONF_METERING_POINTS, []
                )
                existing_selected_sensors = dict(
                    existing_entry.options.get("selected_sensors", {})
                )

                # Add new metering points if they don't exist
                for metering_point in self._metering_points:
                    if metering_point not in existing_metering_points:
                        existing_metering_points.append(metering_point)
                        existing_selected_sensors[metering_point] = (
                            self._selected_sensors[metering_point]
                        )

                # Update the existing entry
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={
                        **existing_entry.data,
                        CONF_METERING_POINTS: existing_metering_points,
                    },
                    options={
                        **dict(existing_entry.options or {}),
                        "selected_sensors": existing_selected_sensors,
                    },
                )

                # Trigger a reload of the config entry
                await self.hass.config_entries.async_reload(existing_entry.entry_id)

                return self.async_abort(reason="config_updated")

            # Create new entry
            return self.async_create_entry(
                title=f"{self._selected_energy_id}",
                data={
                    CONF_API_TOKEN: self._api_token,
                    CONF_ENERGY_ID: self._selected_energy_id,
                    CONF_METERING_POINTS: self._metering_points,
                },
                options={
                    "selected_sensors": self._selected_sensors,
                },
            )
        except Exception:
            _LOGGER.exception("Error finishing configuration")
            return self.async_abort(reason="unknown")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        self._selected_energy_id = entry_data[CONF_ENERGY_ID]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}

        _LOGGER.debug("Starting reauth_confirm step with user_input: %s", user_input)

        if user_input is not None:
            try:
                # Validate the new API token
                _LOGGER.debug(
                    "Creating LenedaClient for reauth with energy_id=%s",
                    self._selected_energy_id,
                )
                client = LenedaClient(
                    api_key=user_input[CONF_API_TOKEN],
                    energy_id=self._selected_energy_id,
                )
                # Test the connection with an existing metering point
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                _LOGGER.debug("Fetched config entry for reauth: %s", entry)
                if entry is None:
                    _LOGGER.error("Reauth failed: config entry not found")
                    return self.async_abort(reason="reauth_failed")

                metering_points = entry.data.get(CONF_METERING_POINTS, [])
                _LOGGER.debug("Metering points for reauth: %s", metering_points)
                if not metering_points:
                    _LOGGER.error("Reauth failed: no metering points in entry")
                    return self.async_abort(reason="reauth_failed")

                # Use get_aggregated_metering_data to test authentication
                obis_code = SENSOR_TYPES["electricity_consumption_active"]["obis_code"]
                end_date = datetime.now()
                start_date = end_date - timedelta(days=7)
                _LOGGER.debug(
                    "Testing authentication with metering_point=%s, obis_code=%s, start_date=%s, end_date=%s",
                    metering_points[0],
                    obis_code,
                    start_date,
                    end_date,
                )

                await self.hass.async_add_executor_job(
                    client.get_aggregated_metering_data,
                    metering_points[0],
                    obis_code,
                    start_date,
                    end_date,
                    "Day",
                    "Accumulation",
                )

                _LOGGER.debug("Reauth successful, updating config entry")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
                )

            except UnauthorizedException:
                _LOGGER.exception("UnauthorizedException during reauth_confirm")
                errors["base"] = ERROR_UNAUTHORIZED
            except ForbiddenException:
                _LOGGER.exception("ForbiddenException during reauth_confirm")
                errors["base"] = ERROR_FORBIDDEN
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth_confirm")
                errors["base"] = ERROR_UNKNOWN

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_TOKEN,
                        description="config.step.reauth_confirm.data.api_token",
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                            autocomplete="leneda-api-token",
                        )
                    ),
                }
            ),
            description_placeholders={
                "energy_id": self._selected_energy_id,
            },
            errors=errors,
        )


class LenedaOptionsFlow(config_entries.OptionsFlow):
    """Handle Leneda options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self._metering_points = config_entry.data.get(CONF_METERING_POINTS, [])
        self._selected_sensors = dict(config_entry.options.get("selected_sensors", {}))
        self._current_metering_point = None
        _LOGGER.debug(
            "Initializing options flow with metering points: %s", self._metering_points
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            if "metering_point" in user_input:
                self._current_metering_point = user_input["metering_point"]
                return await self.async_step_manage_sensors()
            return self.async_create_entry(
                title=self.config_entry.title,
                data=self.config_entry.data,
            )

        # Create options for metering points
        metering_point_options = {mp: mp for mp in self._metering_points}
        _LOGGER.debug("Available metering point options: %s", metering_point_options)

        if not metering_point_options:
            _LOGGER.warning("No metering points found in options flow")
            return self.async_abort(reason="no_metering_points")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "metering_point",
                        default=None,
                        description="config.step.options.data.metering_point",
                    ): vol.In(metering_point_options)
                }
            ),
            description_placeholders={
                "metering_points": "\n".join(f"- {mp}" for mp in self._metering_points)
            },
        )

    async def async_step_manage_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage sensors for a specific metering point."""
        errors = {}

        if user_input is not None:
            try:
                # Get selected sensors
                selected_sensors = user_input.get("sensors", [])

                if not selected_sensors:
                    errors["base"] = ERROR_SELECT_AT_LEAST_ONE
                else:
                    # Update the selected sensors for this metering point
                    self._selected_sensors[self._current_metering_point] = (
                        selected_sensors
                    )

                    # Update the config entry
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        options={
                            **dict(self.config_entry.options or {}),
                            "selected_sensors": self._selected_sensors,
                        },
                    )

                    # Trigger a reload of the config entry
                    await self.hass.config_entries.async_reload(
                        self.config_entry.entry_id
                    )

                    return self.async_create_entry(
                        title=self.config_entry.title,
                        data=self.config_entry.data,
                    )

            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = ERROR_UNKNOWN

        # Get current selected sensors for this metering point
        current_sensors = self._selected_sensors.get(self._current_metering_point, [])

        return self.async_show_form(
            step_id="manage_sensors",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "sensors",
                        default=current_sensors,
                        description="config.step.manage_sensors.data.sensors",
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(SENSOR_TYPES.keys()),
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="sensors",
                        )
                    ),
                }
            ),
            description_placeholders={
                "metering_point": str(self._current_metering_point or "")
            },
            errors=errors,
        )
