"""HMAC-based One-time Password auth module.

Sending HOTP through notify service
"""
import asyncio
from collections import OrderedDict
import logging
from typing import Any, Dict, List, Optional

import attr
import voluptuous as vol

from homeassistant.const import CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers import config_validation as cv

from . import (
    MULTI_FACTOR_AUTH_MODULE_SCHEMA,
    MULTI_FACTOR_AUTH_MODULES,
    MultiFactorAuthModule,
    SetupFlow,
)

REQUIREMENTS = ["pyotp==2.3.0"]

CONF_MESSAGE = "message"

CONFIG_SCHEMA = MULTI_FACTOR_AUTH_MODULE_SCHEMA.extend(
    {
        vol.Optional(CONF_INCLUDE): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_EXCLUDE): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_MESSAGE, default="{} is your Home Assistant login code"): str,
    },
    extra=vol.PREVENT_EXTRA,
)

STORAGE_VERSION = 1
STORAGE_KEY = "auth_module.notify"
STORAGE_USERS = "users"
STORAGE_USER_ID = "user_id"

INPUT_FIELD_CODE = "code"

_LOGGER = logging.getLogger(__name__)


def _generate_secret() -> str:
    """Generate a secret."""
    import pyotp  # pylint: disable=import-outside-toplevel

    return str(pyotp.random_base32())


def _generate_random() -> int:
    """Generate a 8 digit number."""
    import pyotp  # pylint: disable=import-outside-toplevel

    return int(pyotp.random_base32(length=8, chars=list("1234567890")))


def _generate_otp(secret: str, count: int) -> str:
    """Generate one time password."""
    import pyotp  # pylint: disable=import-outside-toplevel

    return str(pyotp.HOTP(secret).at(count))


def _verify_otp(secret: str, otp: str, count: int) -> bool:
    """Verify one time password."""
    import pyotp  # pylint: disable=import-outside-toplevel

    return bool(pyotp.HOTP(secret).verify(otp, count))


@attr.s(slots=True)
class NotifySetting:
    """Store notify setting for one user."""

    secret: str = attr.ib(factory=_generate_secret)  # not persistent
    counter: int = attr.ib(factory=_generate_random)  # not persistent
    notify_service: Optional[str] = attr.ib(default=None)
    target: Optional[str] = attr.ib(default=None)


_UsersDict = Dict[str, NotifySetting]


@MULTI_FACTOR_AUTH_MODULES.register("notify")
class NotifyAuthModule(MultiFactorAuthModule):
    """Auth module send hmac-based one time password by notify service."""

    DEFAULT_TITLE = "Notify One-Time Password"

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]) -> None:
        """Initialize the user data store."""
        super().__init__(hass, config)
        self._user_settings: Optional[_UsersDict] = None
        self._user_store = hass.helpers.storage.Store(
            STORAGE_VERSION, STORAGE_KEY, private=True
        )
        self._include = config.get(CONF_INCLUDE, [])
        self._exclude = config.get(CONF_EXCLUDE, [])
        self._message_template = config[CONF_MESSAGE]
        self._init_lock = asyncio.Lock()

    @property
    def input_schema(self) -> vol.Schema:
        """Validate login flow input data."""
        return vol.Schema({INPUT_FIELD_CODE: str})

    async def _async_load(self) -> None:
        """Load stored data."""
        async with self._init_lock:
            if self._user_settings is not None:
                return

            data = await self._user_store.async_load()

            if data is None:
                data = {STORAGE_USERS: {}}

            self._user_settings = {
                user_id: NotifySetting(**setting)
                for user_id, setting in data.get(STORAGE_USERS, {}).items()
            }

    async def _async_save(self) -> None:
        """Save data."""
        if self._user_settings is None:
            return

        await self._user_store.async_save(
            {
                STORAGE_USERS: {
                    user_id: attr.asdict(
                        notify_setting,
                        filter=attr.filters.exclude(
                            attr.fields(NotifySetting).secret,
                            attr.fields(NotifySetting).counter,
                        ),
                    )
                    for user_id, notify_setting in self._user_settings.items()
                }
            }
        )

    @callback
    def aync_get_available_notify_services(self) -> List[str]:
        """Return list of notify services."""
        unordered_services = set()

        for service in self.hass.services.async_services().get("notify", {}):
            if service not in self._exclude:
                unordered_services.add(service)

        if self._include:
            unordered_services &= set(self._include)

        return sorted(unordered_services)

    async def async_setup_flow(self, user_id: str) -> SetupFlow:
        """Return a data entry flow handler for setup module.

        Mfa module should extend SetupFlow
        """
        return NotifySetupFlow(
            self, self.input_schema, user_id, self.aync_get_available_notify_services()
        )

    async def async_setup_user(self, user_id: str, setup_data: Any) -> Any:
        """Set up auth module for user."""
        if self._user_settings is None:
            await self._async_load()
            assert self._user_settings is not None

        self._user_settings[user_id] = NotifySetting(
            notify_service=setup_data.get("notify_service"),
            target=setup_data.get("target"),
        )

        await self._async_save()

    async def async_depose_user(self, user_id: str) -> None:
        """Depose auth module for user."""
        if self._user_settings is None:
            await self._async_load()
            assert self._user_settings is not None

        if self._user_settings.pop(user_id, None):
            await self._async_save()

    async def async_is_user_setup(self, user_id: str) -> bool:
        """Return whether user is setup."""
        if self._user_settings is None:
            await self._async_load()
            assert self._user_settings is not None

        return user_id in self._user_settings

    async def async_validate(self, user_id: str, user_input: Dict[str, Any]) -> bool:
        """Return True if validation passed."""
        if self._user_settings is None:
            await self._async_load()
            assert self._user_settings is not None

        notify_setting = self._user_settings.get(user_id)
        if notify_setting is None:
            return False

        # user_input has been validate in caller
        return await self.hass.async_add_executor_job(
            _verify_otp,
            notify_setting.secret,
            user_input.get(INPUT_FIELD_CODE, ""),
            notify_setting.counter,
        )

    async def async_initialize_login_mfa_step(self, user_id: str) -> None:
        """Generate code and notify user."""
        if self._user_settings is None:
            await self._async_load()
            assert self._user_settings is not None

        notify_setting = self._user_settings.get(user_id)
        if notify_setting is None:
            raise ValueError("Cannot find user_id")

        def generate_secret_and_one_time_password() -> str:
            """Generate and send one time password."""
            assert notify_setting
            # secret and counter are not persistent
            notify_setting.secret = _generate_secret()
            notify_setting.counter = _generate_random()
            return _generate_otp(notify_setting.secret, notify_setting.counter)

        code = await self.hass.async_add_executor_job(
            generate_secret_and_one_time_password
        )

        await self.async_notify_user(user_id, code)

    async def async_notify_user(self, user_id: str, code: str) -> None:
        """Send code by user's notify service."""
        if self._user_settings is None:
            await self._async_load()
            assert self._user_settings is not None

        notify_setting = self._user_settings.get(user_id)
        if notify_setting is None:
            _LOGGER.error("Cannot find user %s", user_id)
            return

        await self.async_notify(
            code,
            notify_setting.notify_service,  # type: ignore
            notify_setting.target,
        )

    async def async_notify(
        self, code: str, notify_service: str, target: Optional[str] = None
    ) -> None:
        """Send code by notify service."""
        data = {"message": self._message_template.format(code)}
        if target:
            data["target"] = [target]

        await self.hass.services.async_call("notify", notify_service, data)


class NotifySetupFlow(SetupFlow):
    """Handler for the setup flow."""

    def __init__(
        self,
        auth_module: NotifyAuthModule,
        setup_schema: vol.Schema,
        user_id: str,
        available_notify_services: List[str],
    ) -> None:
        """Initialize the setup flow."""
        super().__init__(auth_module, setup_schema, user_id)
        # to fix typing complaint
        self._auth_module: NotifyAuthModule = auth_module
        self._available_notify_services = available_notify_services
        self._secret: Optional[str] = None
        self._count: Optional[int] = None
        self._notify_service: Optional[str] = None
        self._target: Optional[str] = None

    async def async_step_init(
        self, user_input: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Let user select available notify services."""
        errors: Dict[str, str] = {}

        hass = self._auth_module.hass
        if user_input:
            self._notify_service = user_input["notify_service"]
            self._target = user_input.get("target")
            self._secret = await hass.async_add_executor_job(_generate_secret)
            self._count = await hass.async_add_executor_job(_generate_random)

            return await self.async_step_setup()

        if not self._available_notify_services:
            return self.async_abort(reason="no_available_service")

        schema: Dict[str, Any] = OrderedDict()
        schema["notify_service"] = vol.In(self._available_notify_services)
        schema["target"] = vol.Optional(str)

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )

    async def async_step_setup(
        self, user_input: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Verify user can receive one-time password."""
        errors: Dict[str, str] = {}

        hass = self._auth_module.hass
        if user_input:
            verified = await hass.async_add_executor_job(
                _verify_otp, self._secret, user_input["code"], self._count
            )
            if verified:
                await self._auth_module.async_setup_user(
                    self._user_id,
                    {"notify_service": self._notify_service, "target": self._target},
                )
                return self.async_create_entry(title=self._auth_module.name, data={})

            errors["base"] = "invalid_code"

        # generate code every time, no retry logic
        assert self._secret and self._count
        code = await hass.async_add_executor_job(
            _generate_otp, self._secret, self._count
        )

        assert self._notify_service
        try:
            await self._auth_module.async_notify(
                code, self._notify_service, self._target
            )
        except ServiceNotFound:
            return self.async_abort(reason="notify_service_not_exist")

        return self.async_show_form(
            step_id="setup",
            data_schema=self._setup_schema,
            description_placeholders={"notify_service": self._notify_service},
            errors=errors,
        )
