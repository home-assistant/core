"""Adds config flow for Vulcan."""

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientConnectionError
import voluptuous as vol
from vulcan import (
    Account,
    ExpiredTokenException,
    InvalidPINException,
    InvalidSymbolException,
    InvalidTokenException,
    Keystore,
    UnauthorizedCertificateException,
    Vulcan,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PIN, CONF_REGION, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN
from .register import register

_LOGGER = logging.getLogger(__name__)

LOGIN_SCHEMA = {
    vol.Required(CONF_TOKEN): str,
    vol.Required(CONF_REGION): str,
    vol.Required(CONF_PIN): str,
}


class VulcanFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Uonet+ Vulcan config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self.account = None
        self.keystore = None
        self.students = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle config flow."""
        if self._async_current_entries():
            return await self.async_step_add_next_config_entry()

        return await self.async_step_auth()

    async def async_step_auth(self, user_input=None, errors=None):
        """Authorize integration."""

        if user_input is not None:
            try:
                credentials = await register(
                    self.hass,
                    user_input[CONF_TOKEN],
                    user_input[CONF_REGION],
                    user_input[CONF_PIN],
                )
            except InvalidSymbolException:
                errors = {"base": "invalid_symbol"}
            except InvalidTokenException:
                errors = {"base": "invalid_token"}
            except InvalidPINException:
                errors = {"base": "invalid_pin"}
            except ExpiredTokenException:
                errors = {"base": "expired_token"}
            except ClientConnectionError as err:
                errors = {"base": "cannot_connect"}
                _LOGGER.error("Connection error: %s", err)
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors = {"base": "unknown"}
            if not errors:
                account = credentials["account"]
                keystore = credentials["keystore"]
                client = Vulcan(keystore, account, async_get_clientsession(self.hass))
                students = await client.get_students()

                if len(students) > 1:
                    self.account = account
                    self.keystore = keystore
                    self.students = students
                    return await self.async_step_select_student()
                student = students[0]
                await self.async_set_unique_id(str(student.pupil.id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{student.pupil.first_name} {student.pupil.last_name}",
                    data={
                        "student_id": str(student.pupil.id),
                        "keystore": keystore.as_dict,
                        "account": account.as_dict,
                    },
                )

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(LOGIN_SCHEMA),
            errors=errors,
        )

    async def async_step_select_student(self, user_input=None):
        """Allow user to select student."""
        errors = {}
        students = {}
        if self.students is not None:
            for student in self.students:
                students[str(student.pupil.id)] = (
                    f"{student.pupil.first_name} {student.pupil.last_name}"
                )
        if user_input is not None:
            student_id = user_input["student"]
            await self.async_set_unique_id(str(student_id))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=students[student_id],
                data={
                    "student_id": str(student_id),
                    "keystore": self.keystore.as_dict,
                    "account": self.account.as_dict,
                },
            )

        return self.async_show_form(
            step_id="select_student",
            data_schema=vol.Schema({vol.Required("student"): vol.In(students)}),
            errors=errors,
        )

    async def async_step_select_saved_credentials(self, user_input=None, errors=None):
        """Allow user to select saved credentials."""

        credentials = {}
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            credentials[entry.entry_id] = entry.data["account"]["UserName"]

        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(user_input["credentials"])
            keystore = Keystore.load(entry.data["keystore"])
            account = Account.load(entry.data["account"])
            client = Vulcan(keystore, account, async_get_clientsession(self.hass))
            try:
                students = await client.get_students()
            except UnauthorizedCertificateException:
                return await self.async_step_auth(
                    errors={"base": "expired_credentials"}
                )
            except ClientConnectionError as err:
                _LOGGER.error("Connection error: %s", err)
                return await self.async_step_select_saved_credentials(
                    errors={"base": "cannot_connect"}
                )
            except Exception:
                _LOGGER.exception("Unexpected exception")
                return await self.async_step_auth(errors={"base": "unknown"})
            if len(students) == 1:
                student = students[0]
                await self.async_set_unique_id(str(student.pupil.id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{student.pupil.first_name} {student.pupil.last_name}",
                    data={
                        "student_id": str(student.pupil.id),
                        "keystore": keystore.as_dict,
                        "account": account.as_dict,
                    },
                )
            self.account = account
            self.keystore = keystore
            self.students = students
            return await self.async_step_select_student()

        data_schema = {
            vol.Required(
                "credentials",
            ): vol.In(credentials),
        }
        return self.async_show_form(
            step_id="select_saved_credentials",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_add_next_config_entry(self, user_input=None):
        """Flow initialized when user is adding next entry of that integration."""

        existing_entries = self.hass.config_entries.async_entries(DOMAIN)

        errors = {}

        if user_input is not None:
            if not user_input["use_saved_credentials"]:
                return await self.async_step_auth()
            if len(existing_entries) > 1:
                return await self.async_step_select_saved_credentials()
            keystore = Keystore.load(existing_entries[0].data["keystore"])
            account = Account.load(existing_entries[0].data["account"])
            client = Vulcan(keystore, account, async_get_clientsession(self.hass))
            students = await client.get_students()
            existing_entry_ids = [
                entry.data["student_id"] for entry in existing_entries
            ]
            new_students = [
                student
                for student in students
                if str(student.pupil.id) not in existing_entry_ids
            ]
            if not new_students:
                return self.async_abort(reason="all_student_already_configured")
            if len(new_students) == 1:
                await self.async_set_unique_id(str(new_students[0].pupil.id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=(
                        f"{new_students[0].pupil.first_name} {new_students[0].pupil.last_name}"
                    ),
                    data={
                        "student_id": str(new_students[0].pupil.id),
                        "keystore": keystore.as_dict,
                        "account": account.as_dict,
                    },
                )
            self.account = account
            self.keystore = keystore
            self.students = new_students
            return await self.async_step_select_student()

        data_schema = {
            vol.Required("use_saved_credentials", default=True): bool,
        }
        return self.async_show_form(
            step_id="add_next_config_entry",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Reauthorize integration."""
        errors = {}
        if user_input is not None:
            try:
                credentials = await register(
                    self.hass,
                    user_input[CONF_TOKEN],
                    user_input[CONF_REGION],
                    user_input[CONF_PIN],
                )
            except InvalidSymbolException:
                errors = {"base": "invalid_symbol"}
            except InvalidTokenException:
                errors = {"base": "invalid_token"}
            except InvalidPINException:
                errors = {"base": "invalid_pin"}
            except ExpiredTokenException:
                errors = {"base": "expired_token"}
            except ClientConnectionError as err:
                errors["base"] = "cannot_connect"
                _LOGGER.error("Connection error: %s", err)
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            if not errors:
                account = credentials["account"]
                keystore = credentials["keystore"]
                client = Vulcan(keystore, account, async_get_clientsession(self.hass))
                students = await client.get_students()
                existing_entries = self.hass.config_entries.async_entries(DOMAIN)
                matching_entries = False
                for student in students:
                    for entry in existing_entries:
                        if str(student.pupil.id) == str(entry.data["student_id"]):
                            self.hass.config_entries.async_update_entry(
                                entry,
                                title=(
                                    f"{student.pupil.first_name} {student.pupil.last_name}"
                                ),
                                data={
                                    "student_id": str(student.pupil.id),
                                    "keystore": keystore.as_dict,
                                    "account": account.as_dict,
                                },
                            )
                            await self.hass.config_entries.async_reload(entry.entry_id)
                            matching_entries = True
                if not matching_entries:
                    return self.async_abort(reason="no_matching_entries")
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(LOGIN_SCHEMA),
            errors=errors,
        )
