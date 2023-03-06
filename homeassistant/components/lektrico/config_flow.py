"""Config flow for Lektrico Charging Station."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import lektricowifi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class LektricoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Lektrico config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str | None = None
        self._friendly_name: str | None = None
        self._serial_number: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> LektricoOptionsFlowHandler:
        """Get the options flow for this handler."""
        return LektricoOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._async_show_setup_form()

        self._host = user_input[CONF_HOST]
        self._friendly_name = user_input[CONF_FRIENDLY_NAME]

        # obtain serial number
        try:
            await self._get_lektrico_serial_number_and_treat_unique_id(
                raise_on_progress=True
            )
        except lektricowifi.DeviceConnectionError:
            return self._async_show_setup_form({"base": "cannot_connect"})

        return self._async_create_entry()

    async def async_step_config(self) -> FlowResult:
        """Confirm the setup."""

        return self.async_show_form(
            step_id="config",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FRIENDLY_NAME): str,
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors={},
        )

    @callback
    def _async_show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FRIENDLY_NAME): str,
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors or {},
        )

    @callback
    def _async_create_entry(self) -> FlowResult:
        return self.async_create_entry(
            title=f"{self._friendly_name}_{str(self._serial_number)}",
            data={CONF_HOST: self._host, CONF_FRIENDLY_NAME: self._friendly_name},
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        self._host = discovery_info.host  # 192.168.100.11
        _id = discovery_info.properties.get("id")  # 1p7k_500006

        if _id is None:
            # properties have no "id"
            return self.async_abort(reason="missing_id")
        _index = _id.find("_")
        if _index == -1:
            # "id" does not contain "_"
            return self.async_abort(reason="missing_underline_in_id")
        self._friendly_name = _id[:_index]  # it's the type
        self._serial_number = _id[_index + 1 :]

        # Set unique id
        await self.async_set_unique_id(self._serial_number, raise_on_progress=True)
        # Abort if already configured, but update the last-known host
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host}, reload_on_update=True
        )

        self.context["title_placeholders"] = {
            "serial_number": self._serial_number,
            "friendly_name": self._friendly_name,
        }

        return await self.async_step_confirm()

    async def _get_lektrico_serial_number_and_treat_unique_id(
        self, raise_on_progress: bool = True
    ) -> None:
        """Get device's serial number from a Lektrico device."""
        session = async_get_clientsession(self.hass)
        device = lektricowifi.Device(
            _host=self._host,
            session=session,
        )

        settings = await device.device_config()

        # Check if already configured
        await self.async_set_unique_id(
            settings.serial_number, raise_on_progress=raise_on_progress
        )

        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host}, reload_on_update=True
        )

        self._serial_number = settings.serial_number

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Allow the user to confirm adding the device."""

        if user_input is not None:
            return self.async_create_entry(
                title=f"{self._friendly_name}_{str(self._serial_number)}",
                data={CONF_HOST: self._host, CONF_FRIENDLY_NAME: self._friendly_name},
            )

        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")


class LektricoOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Lektrico device options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Lektrico device options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the Lektrico device options."""
        errors: dict[str, str] = {}
        options = dict(self.config_entry.options)

        if user_input is not None:
            _old_friendly_name: str = self.config_entry.data[CONF_FRIENDLY_NAME]
            friendly_name = user_input[CONF_FRIENDLY_NAME]
            options[CONF_FRIENDLY_NAME] = friendly_name

            updated_config = dict(
                self.config_entry.data
            )  # {'host': '192.168.100.11', 'friendly_name': 'asd'}
            updated_config[CONF_FRIENDLY_NAME] = friendly_name

            # get the serial number from the old title
            _index_sn: int = self.config_entry.title.rfind("_")
            _taken_serial_number: str = ""
            if _index_sn != -1:
                _taken_serial_number = self.config_entry.title[_index_sn + 1 :]
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=updated_config,
                title=f"{friendly_name}_{_taken_serial_number}",
            )

            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            ent_reg = entity_registry.async_get(self.hass)
            device_registry.async_get(self.hass)
            for entity_entry in list(ent_reg.entities.values()):
                if entity_entry.config_entry_id == self.config_entry.entry_id:
                    # it's the entity of my device => rename it
                    _old_entity_id: str = entity_entry.entity_id
                    _friendly_name_index: int = _old_entity_id.find(_old_friendly_name)

                    _new_entity_id: str = "{}{}{}".format(
                        _old_entity_id[:_friendly_name_index],
                        friendly_name,
                        _old_entity_id[
                            _friendly_name_index + len(_old_friendly_name) :
                        ],
                    )

                    ent_reg.async_update_entity(
                        entity_entry.entity_id, new_entity_id=_new_entity_id
                    )

            return self.async_create_entry(title="", data=options)

        fields = {}

        def _add_with_suggestion(key: str, validator: Callable | type[bool]) -> None:
            """Add a field to with a suggested value.

            For bools, use the existing value as default, or fallback to False.
            """
            if validator is bool:
                fields[vol.Required(key, default=options.get(key, False))] = validator
            elif (suggested_value := options.get(key)) is None:
                fields[vol.Optional(key)] = validator
            else:
                fields[
                    vol.Optional(key, description={"suggested_value": suggested_value})
                ] = validator

        _add_with_suggestion(CONF_FRIENDLY_NAME, str)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(fields),
            errors=errors,
        )
