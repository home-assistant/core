"""Adds config flow for Vulcan."""
import logging
import os

from aiohttp import ClientConnectorError
import voluptuous as vol
from vulcan import Account, Keystore, Vulcan
from vulcan._utils import VulcanAPIException

from homeassistant import config_entries
from homeassistant.const import CONF_PIN, CONF_REGION, CONF_SCAN_INTERVAL, CONF_TOKEN
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import DOMAIN
from .const import DEFAULT_SCAN_INTERVAL
from .register import register

_LOGGER = logging.getLogger(__name__)

LOGIN_SCHEMA = {
    vol.Required(CONF_TOKEN): str,
    vol.Required(CONF_REGION): str,
    vol.Required(CONF_PIN): str,
}


class VulcanFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Uonet+ Vulcan config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return VulcanOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle config flow."""
        if self._async_current_entries():
            return await self.async_step_add_next_config_entry()

        return await self.async_step_auth()

    async def async_step_auth(self, user_input=None, errors=None):
        """Authorize integration."""
        if errors is None:
            errors = {}

        if user_input is not None:
            try:
                credentials = await register(
                    self.hass,
                    user_input[CONF_TOKEN],
                    user_input[CONF_REGION],
                    user_input[CONF_PIN],
                )
            except VulcanAPIException as err:
                if str(err) == "Invalid token!" or str(err) == "Invalid token.":
                    errors["base"] = "invalid_token"
                elif str(err) == "Expired token.":
                    errors["base"] = "expired_token"
                elif str(err) == "Invalid PIN.":
                    errors["base"] = "invalid_pin"
                else:
                    errors["base"] = "unknown"
                    _LOGGER.error(err)
            except RuntimeError as err:
                if str(err) == "Internal Server Error (ArgumentException)":
                    errors["base"] = "invalid_symbol"
                else:
                    errors["base"] = "unknown"
                    _LOGGER.error(err)
            except ClientConnectorError as err:
                errors["base"] = "cannot_connect"
                _LOGGER.error("Connection error: %s", err)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            if errors == {}:
                account = credentials["account"]
                keystore = credentials["keystore"]
                client = Vulcan(keystore, account)
                _students = await client.get_students()
                await client.close()

                if len(_students) > 1:
                    return await self.async_step_select_student(account, _students)
                _student = _students[0]
                await self.async_set_unique_id(str(_student.pupil.id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{_student.pupil.first_name} {_student.pupil.last_name}",
                    data={
                        "student_id": str(_student.pupil.id),
                        "login": account.user_login,
                    },
                )

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(LOGIN_SCHEMA),
            errors=errors,
        )

    async def async_step_select_student(
        self, user_input=None, account=None, _students=None
    ):
        """Allow user to select student."""
        errors = {}
        students_list = {}
        if _students is not None:
            for student in _students:
                students_list[
                    str(student.pupil.id)
                ] = f"{student.pupil.first_name} {student.pupil.last_name}"
        if user_input is not None:
            student_id = user_input["student"]
            await self.async_set_unique_id(str(student_id))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=students_list[student_id],
                data={
                    "student_id": str(student_id),
                    "login": account.user_login,
                },
            )

        data_schema = {
            vol.Required(
                "student",
            ): vol.In(students_list),
        }
        return self.async_show_form(
            step_id="select_student",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_select_saved_credentials(self, user_input=None):
        """Allow user to select saved credentials."""
        errors = {}
        credentials_list = {}
        file_list = os.listdir(".vulcan")
        for file in file_list:
            if file.startswith("account-") and file.endswith(".json"):
                if file.replace("account", "keystore") in file_list:
                    credentials_list[os.path.join(".vulcan", file)] = file[
                        len("account-") :
                    ][: -len(".json")]

        if user_input is not None:
            with open(user_input["credentials"].replace("account", "keystore")) as file:
                keystore = Keystore.load(file)
            with open(user_input["credentials"]) as file:
                account = Account.load(file)
            client = Vulcan(keystore, account)
            try:
                _students = await client.get_students()
            except VulcanAPIException as err:
                if str(err) == "The certificate is not authorized.":
                    os.remove(user_input["credentials"])
                    os.remove(user_input["credentials"].replace("account", "keystore"))
                    return await self.async_step_auth(
                        errors={"base": "expired_credentials"}
                    )
                _LOGGER.error(err)
                return await self.async_step_auth(errors={"base": "unknown"})
            except ClientConnectorError as err:
                _LOGGER.error("Connection error: %s", err)
                return await self.async_step_auth(errors={"base": "cannot_connect"})
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return await self.async_step_auth(errors={"base": "unknown"})
            finally:
                await client.close()
            if len(_students) == 1:
                _student = _students[0]
                await self.async_set_unique_id(str(_student.pupil.id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{_student.pupil.first_name} {_student.pupil.last_name}",
                    data={
                        "student_id": str(_student.pupil.id),
                        "login": account.user_login,
                    },
                )
            return await self.async_step_select_student(account, _students)

        data_schema = {
            vol.Required(
                "credentials",
            ): vol.In(credentials_list),
        }
        return self.async_show_form(
            step_id="select_saved_credentials",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_add_next_config_entry(self, user_input=None):
        """Flow initialized when user is adding next entry of that integration."""
        if os.path.exists(".vulcan"):
            file_list = os.listdir(".vulcan")
            if len(file_list) < 2:
                return await self.async_step_auth()

            valid_credentials_list = []
            for file in file_list:
                if file.startswith("account-") and file.endswith(".json"):
                    if file.replace("account", "keystore") in file_list:
                        valid_credentials_list.append(
                            file[len("account-") :][: -len(".json")]
                        )
            if valid_credentials_list == []:
                return await self.async_step_auth()

        errors = {}
        if user_input is not None:
            if user_input["use_saved_credentials"]:
                if len(valid_credentials_list) == 1:
                    with open(
                        f".vulcan/keystore-{valid_credentials_list[0]}.json"
                    ) as _file:
                        keystore = Keystore.load(_file)
                    with open(
                        f".vulcan/account-{valid_credentials_list[0]}.json"
                    ) as _file:
                        account = Account.load(_file)
                    client = Vulcan(keystore, account)
                    _students = await client.get_students()
                    await client.close()
                    new_students = []
                    existing_entry_ids = []
                    for entry in self.hass.config_entries.async_entries(DOMAIN):
                        existing_entry_ids.append(entry.data.get("student_id"))
                    for student in _students:
                        if not str(student.pupil.id) in existing_entry_ids:
                            new_students.append(student)
                    if new_students == []:
                        return self.async_abort(reason="all_student_already_configured")
                    if len(new_students) == 1:
                        await self.async_set_unique_id(str(new_students[0].pupil.id))
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title=f"{new_students[0].pupil.first_name} {new_students[0].pupil.last_name}",
                            data={
                                "student_id": str(new_students[0].pupil.id),
                                "login": account.user_login,
                            },
                        )
                    return await self.async_step_select_student(
                        account=account, _students=new_students
                    )
                return await self.async_step_select_saved_credentials()
            return await self.async_step_auth()

        data_schema = {
            vol.Required("use_saved_credentials", default=True): bool,
        }
        return self.async_show_form(
            step_id="add_next_config_entry",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_reauth(self, user_input=None):
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
            except VulcanAPIException as err:
                if str(err) == "Invalid token!" or str(err) == "Invalid token.":
                    errors["base"] = "invalid_token"
                elif str(err) == "Expired token.":
                    errors["base"] = "expired_token"
                elif str(err) == "Invalid PIN.":
                    errors["base"] = "invalid_pin"
                else:
                    errors["base"] = "unknown"
                    _LOGGER.error(err)
            except RuntimeError as err:
                if str(err) == "Internal Server Error (ArgumentException)":
                    errors["base"] = "invalid_symbol"
                else:
                    errors["base"] = "unknown"
                    _LOGGER.error(err)
            except ClientConnectorError as err:
                errors["base"] = "cannot_connect"
                _LOGGER.error("Connection error: %s", err)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            if errors == {}:
                account = credentials["account"]
                keystore = credentials["keystore"]
                client = Vulcan(keystore, account)
                students = await client.get_students()
                await client.close()
                for student in students:
                    for entry_id in self._async_current_ids():
                        if str(student.pupil.id) == str(entry_id):
                            existing_entry = await self.async_set_unique_id(
                                str(student.pupil.id)
                            )
                            self.hass.config_entries.async_update_entry(
                                existing_entry,
                                title=f"{student.pupil.first_name} {student.pupil.last_name}",
                                data={
                                    "login": account.user_login,
                                    "student_id": str(student.pupil.id),
                                },
                            )
                            await self.hass.config_entries.async_reload(
                                existing_entry.entry_id
                            )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth",
            data_schema=vol.Schema(LOGIN_SCHEMA),
            errors=errors,
        )


class VulcanOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for Uonet+ Vulcan."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): cv.positive_int,
        }

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options), errors=errors
        )
