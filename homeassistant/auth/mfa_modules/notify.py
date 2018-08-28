"""HMAC-based One-time Password auth module.

Sending HOTP through notify service
"""
import logging
from collections import OrderedDict
from random import SystemRandom
from typing import Any, Dict, Optional, Tuple, List  # noqa: F401

import voluptuous as vol

from homeassistant.const import CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from . import MultiFactorAuthModule, MULTI_FACTOR_AUTH_MODULES, \
    MULTI_FACTOR_AUTH_MODULE_SCHEMA, SetupFlow

REQUIREMENTS = ['pyotp==2.2.6']

CONF_MESSAGE = 'message'

CONFIG_SCHEMA = MULTI_FACTOR_AUTH_MODULE_SCHEMA.extend({
    vol.Optional(CONF_INCLUDE): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_EXCLUDE): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_MESSAGE, default='Your Home Assistant One-time Password'
                                       ' is "{}"'): str
}, extra=vol.PREVENT_EXTRA)

STORAGE_VERSION = 1
STORAGE_KEY = 'auth_module.notify'
STORAGE_USERS = 'users'
STORAGE_USER_ID = 'user_id'
STORAGE_OTA_SECRET = 'ota_secret'
STORAGE_COUNTER = 'counter'

INPUT_FIELD_CODE = 'code'

DUMMY_SECRET = '7Z5EFWI4RFLVV67G'

_LOGGER = logging.getLogger(__name__)

_UsersDict = Dict[str, Tuple[str, int, Optional[str], Optional[str]]]


def _generate_secret_and_init_counter() -> Tuple[str, int]:
    """Generate a secret and a random initial counter."""
    import pyotp

    ota_secret = pyotp.random_base32()
    counter = SystemRandom().randint(0, 2 << 31)
    return ota_secret, counter


def _generate_otp(secret: str, count: int) -> str:
    """Generate one time password."""
    import pyotp

    return str(pyotp.HOTP(secret).at(count))


def _verify_otp(secret: str, otp: str, counter: int) -> bool:
    """Verify one time password."""
    import pyotp

    return bool(pyotp.HOTP(secret).verify(otp, counter))


@MULTI_FACTOR_AUTH_MODULES.register('notify')
class NotifyAuthModule(MultiFactorAuthModule):
    """Auth module send hmac-based one time password by notify service."""

    DEFAULT_TITLE = 'Notify One-Time Password'

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]) -> None:
        """Initialize the user data store."""
        super().__init__(hass, config)
        self._users = None  # type: Optional[_UsersDict]
        self._user_store = hass.helpers.storage.Store(
            STORAGE_VERSION, STORAGE_KEY)
        self._include = config.get(CONF_INCLUDE, [])
        self._exclude = config.get(CONF_EXCLUDE, [])
        self._message_template = config[CONF_MESSAGE]

    @property
    def input_schema(self) -> vol.Schema:
        """Validate login flow input data."""
        return vol.Schema({INPUT_FIELD_CODE: str})

    async def _async_load(self) -> None:
        """Load stored data."""
        data = await self._user_store.async_load()

        if data is None:
            data = {STORAGE_USERS: {}}

        self._users = data.get(STORAGE_USERS, {})

    async def _async_save(self) -> None:
        """Save data."""
        await self._user_store.async_save({STORAGE_USERS: self._users})

    def _add_user_setup_data(self, user_id: str,
                             secret: Optional[str] = None,
                             counter: int = 0,
                             notify_service: Optional[str] = None,
                             target: Optional[str] = None) -> None:
        """Create a ota_secret for user."""
        import pyotp

        ota_secret = secret or pyotp.random_base32()  # type: str
        init_counter = counter

        self._users[user_id] = (ota_secret, init_counter,   # type: ignore
                                notify_service, target)

    @callback
    def aync_get_aviliable_notify_services(self) -> List[str]:
        """Return list of notify services."""
        unordered_services = [
            service_id for service_id in
            self.hass.services.async_services().get(
                'notify', {}).keys()]

        for exclude_service in self._exclude:
            if exclude_service in unordered_services:
                unordered_services.remove(exclude_service)

        if self._include:
            unordered_services = [s for s in self._include
                                  if s in unordered_services]

        return sorted(unordered_services)

    async def async_setup_flow(self, user_id: str) -> SetupFlow:
        """Return a data entry flow handler for setup module.

        Mfa module should extend SetupFlow
        """
        return NotifySetupFlow(
            self, self.input_schema, user_id,
            self.aync_get_aviliable_notify_services())

    async def async_setup_user(self, user_id: str, setup_data: Any) -> Any:
        """Set up auth module for user."""
        if self._users is None:
            await self._async_load()

        await self.hass.async_add_executor_job(
            self._add_user_setup_data, user_id,
            setup_data.get('secret'),
            int(setup_data.get('counter', 0)),
            setup_data.get('notify_service'),
            setup_data.get('target'),
        )

        await self._async_save()

    async def async_depose_user(self, user_id: str) -> None:
        """Depose auth module for user."""
        if self._users is None:
            await self._async_load()

        if self._users.pop(user_id, None):   # type: ignore
            await self._async_save()

    async def async_is_user_setup(self, user_id: str) -> bool:
        """Return whether user is setup."""
        if self._users is None:
            await self._async_load()

        return user_id in self._users   # type: ignore

    async def async_validate(
            self, user_id: str, user_input: Dict[str, Any]) -> bool:
        """Return True if validation passed."""
        if self._users is None:
            await self._async_load()

        # user_input has been validate in caller
        result = await self.hass.async_add_executor_job(
            self._validate_one_time_password, user_id,
            user_input.get(INPUT_FIELD_CODE, ''))

        # save user data no matter if passed validation to update counter
        await self._async_save()

        return result

    def _validate_one_time_password(self, user_id: str, code: str) -> bool:
        """Validate one time password."""
        ota_secret, counter, notify_service, target = \
            self._users.get(user_id, (None, 0, None, None))  # type: ignore
        if ota_secret is None:
            # even we cannot find user, we still do verify
            # to make timing the same as if user was found.
            _verify_otp(DUMMY_SECRET, code, 0)
            return False

        result = _verify_otp(ota_secret, code, counter)

        # move counter no matter if passed validation
        self._users[user_id] = (ota_secret, counter + 1,  # type: ignore
                                notify_service, target)
        return result

    async def async_generate(self, user_id: str) -> Optional[str]:
        """Generate code and notify user."""
        if self._users is None:
            await self._async_load()

        code = await self.hass.async_add_executor_job(
            self._generate_and_send_one_time_password, user_id)

        await self.async_notify_user(user_id, code)

        # Do not return code, code has delivered by notify service
        return None

    def _generate_and_send_one_time_password(self, user_id: str) -> str:
        """Generate and send one time password."""
        ota_secret, counter, _, _ = \
            self._users.get(user_id, (None, 0, None, None))  # type: ignore
        if ota_secret is None:
            raise ValueError('Cannot find user_id')

        return _generate_otp(ota_secret, counter)

    async def async_notify_user(self, user_id: str, code: str) -> None:
        """Send code by user's notify service."""
        if self._users is None:
            await self._async_load()

        _, _, notify_service, target = \
            self._users.get(user_id, (None, 0, None, None))  # type: ignore

        if notify_service is None:
            _LOGGER.error('Cannot find user %s', user_id)
            return

        await self.async_notify(code, notify_service, target)

    async def async_notify(self, code: str, notify_service: str,
                           target: Optional[str] = None) -> None:
        """Send code by notify service."""
        data = {'message': self._message_template.format(code)}
        if target:
            data['target'] = [target]

        await self.hass.services.async_call('notify', notify_service, data)


class NotifySetupFlow(SetupFlow):
    """Handler for the setup flow."""

    def __init__(self, auth_module: NotifyAuthModule,
                 setup_schema: vol.Schema,
                 user_id: str,
                 available_notify_services: List[str]) -> None:
        """Initialize the setup flow."""
        super().__init__(auth_module, setup_schema, user_id)
        # to fix typing complaint
        self._auth_module = auth_module  # type: NotifyAuthModule
        self._available_notify_services = available_notify_services
        self._ota_secret = None  # type: Optional[str]
        self._counter = None  # type Optional[int]
        self._notify_service = None  # type: Optional[str]
        self._target = None  # type: Optional[str]

    async def async_step_init(
            self, user_input: Optional[Dict[str, str]] = None) \
            -> Dict[str, Any]:
        """Handle the first step of setup flow.

        Return self.async_show_form(step_id='init') if user_input == None.
        Return self.async_create_entry(data={'result': result}) if finish.
        """
        errors = {}  # type: Dict[str, str]

        hass = self._auth_module.hass
        if user_input:
            self._notify_service = user_input['notify_service']
            self._target = user_input.get('target')

            return await self.async_step_setup()

        if not self._available_notify_services:
            return self.async_abort(reason='no_available_service')

        self._ota_secret, self._counter = \
            await hass.async_add_executor_job(  # type: ignore
                _generate_secret_and_init_counter)

        schema = OrderedDict()  # type: Dict[str, Any]
        schema['notify_service'] = vol.In(self._available_notify_services)
        schema['target'] = vol.Optional(str)

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema(schema),
            errors=errors
        )

    async def async_step_setup(
            self, user_input: Optional[Dict[str, str]] = None) \
            -> Dict[str, Any]:
        """Handle the setup step of setup flow.

        Return self.async_show_form(step_id='init') if user_input == None.
        Return self.async_create_entry(data={'result': result}) if finish.
        """
        import pyotp

        errors = {}  # type: Dict[str, str]

        if user_input:
            hass = self._auth_module.hass
            verified = await hass.async_add_executor_job(
                pyotp.HOTP(self._ota_secret).verify,
                user_input['code'], self._counter)
            self._counter += 1  # type: ignore
            if verified:
                result = await self._auth_module.async_setup_user(
                    self._user_id, {
                        'secret': self._ota_secret,
                        'counter': self._counter,  # counter has increased
                        'notify_service': self._notify_service,
                        'target': self._target,
                    })
                return self.async_create_entry(
                    title=self._auth_module.name,
                    data={'result': result}
                )

            errors['base'] = 'invalid_code'

        code = _generate_otp(self._ota_secret, self._counter)  # type: ignore

        await self._auth_module.async_notify(  # type: ignore
            code, self._notify_service, self._target)

        return self.async_show_form(
            step_id='setup',
            data_schema=self._setup_schema,
            description_placeholders={'notify_service': self._notify_service},
            errors=errors
        )
