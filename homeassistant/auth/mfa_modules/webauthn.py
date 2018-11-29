"""WebAuthn-based auth module."""
import base64
import logging
import string
from typing import Any, Dict, Optional, Tuple

import voluptuous as vol

from homeassistant.auth.models import User
from homeassistant.core import HomeAssistant

from . import (
    MULTI_FACTOR_AUTH_MODULE_SCHEMA, MULTI_FACTOR_AUTH_MODULES,
    MultiFactorAuthModule, SetupFlow)

# TODO: Update version after release (and in requirements_all.txt and requirements_test_all.txt)
# TODO: Tests
# TODO: Проверить что работает при смене домена
#REQUIREMENTS = ['fido2==0.4.0']
REQUIREMENTS = ['https://github.com/Yubico/python-fido2.git#fido2==0.4.0']

CONFIG_SCHEMA = MULTI_FACTOR_AUTH_MODULE_SCHEMA.extend({
}, extra=vol.PREVENT_EXTRA)

STORAGE_VERSION = 1
STORAGE_KEY = 'auth_module.webauthn'
STORAGE_USERS = 'users'
STORAGE_USER_ID = 'user_id'

INPUT_FIELD_TOKEN = 'token'
INPUT_FIELD_ERROR = 'error'

INPUT_ERROR_UNSUPPORTED = 'unsupported'
INPUT_ERROR_PROTOCOL = 'protocol'
INPUT_ERROR_CREDENTIALS = 'credentials'
INPUT_ERROR_CANCELLED = 'cancelled'

_LOGGER = logging.getLogger(__name__)


def _create_server(hass: HomeAssistant) -> Any:
    """Create Fido2Server for authentication."""
    from fido2.server import Fido2Server, RelyingParty
    from urllib.parse import urlparse

    parsed_uri = urlparse(hass.config.api.base_url)
    rp = RelyingParty(parsed_uri.hostname)
    return Fido2Server(rp)


def _encode_bytes_to_string(data: Any) -> string:
    """Encode bytes to UTF-8 string with CBOR and BASE64."""
    from fido2 import cbor

    encoded = base64.encodebytes(cbor.dumps(data))
    return encoded.decode('utf-8')


def _decode_string_to_bytes(data: str) -> Any:
    """Decode UTF-8 string to bytes from CBOR and BASE64."""
    from fido2 import cbor

    decoded = base64.decodebytes(data.encode('utf-8'))
    return cbor.loads(decoded)[0]


def _get_create_data(token: str) -> Tuple[Any, Any]:
    """Provide data for registration."""
    from fido2.client import ClientData
    from fido2.ctap2 import AttestationObject

    data = _decode_string_to_bytes(token)
    client_data = ClientData(data['clientDataJSON'])
    att_obj = AttestationObject(data['attestationObject'])
    return client_data, att_obj


def _get_validate_data(token: str) -> Tuple[Any, Any, Any, Any]:
    """Provide data for validating token."""
    from fido2.client import ClientData
    from fido2.ctap2 import AuthenticatorData

    data = _decode_string_to_bytes(token)
    credential_id = data['credentialId']
    client_data = ClientData(data['clientDataJSON'])
    auth_data = AuthenticatorData(data['authenticatorData'])
    signature = data['signature']
    return credential_id, client_data, auth_data, signature


def _decode_credentials(credentials: list) -> list:
    """Create AttestedCredentialData from saved credentials."""
    from fido2.ctap2 import AttestedCredentialData

    return list(map(
        lambda item: AttestedCredentialData(_decode_string_to_bytes(item)),
        credentials
    ))


def _encode_credentials(credentials: list) -> list:
    """Create encoded credentials for saving."""
    return list(map(lambda item: _encode_bytes_to_string(item), credentials))


@MULTI_FACTOR_AUTH_MODULES.register('webauthn')
class WebAuthnAuthModule(MultiFactorAuthModule):
    """Auth module validate hardware tokens using WebAuthn."""

    DEFAULT_TITLE = 'Web Authentication'
    MAX_RETRY_TIME = 3
    MULTIPLE = True

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]) -> None:
        """Initialize the user data store."""
        super().__init__(hass, config)

        self._users = None  # type: Optional[Dict[str, list]]
        self._user_store = hass.helpers.storage.Store(
            STORAGE_VERSION, STORAGE_KEY, private=True)
        self._server = None  # type: fido2.server.Fido2Server
        self._challenge = None  # type: str

    @property
    def input_schema(self) -> vol.Schema:
        """Don't need form - don't use schema."""
        return vol.Schema({}, extra=vol.ALLOW_EXTRA)

    async def _async_load(self) -> None:
        """Load stored data if needed."""
        if self._users is None:
            data = await self._user_store.async_load()

            if data is None:
                data = {STORAGE_USERS: {}}

            self._users = data.get(STORAGE_USERS, {})

    async def _async_save(self) -> None:
        """Save data."""
        await self._user_store.async_save({STORAGE_USERS: self._users})

    async def async_get_count(self, user_id: str) -> int:
        """Return count of added keys for multiple auth module."""
        await self._async_load()
        return len(self._users.get(user_id, []))

    async def async_setup_flow(self, user_id: str) -> SetupFlow:
        """Return a data entry flow handler for setup module."""
        await self._async_load()

        credentials_encoded = self._users.get(user_id, None)
        credentials = [] if credentials_encoded is None \
            else _decode_credentials(credentials_encoded)

        user = await self.hass.auth.async_get_user(user_id)   # type: ignore
        return WebAuthnSetupFlow(self, self.input_schema, user, credentials)

    async def async_setup_user(self, user_id: str, setup_data: list) -> Any:
        """Set up auth module for user."""
        await self._async_load()
        self._users[user_id] = _encode_credentials(setup_data)
        await self._async_save()

    async def async_depose_user(self, user_id: str) -> None:
        """Depose auth module for user."""
        await self._async_load()
        if self._users.pop(user_id, None):   # type: ignore
            await self._async_save()

    async def async_is_user_setup(self, user_id: str) -> bool:
        """Return whether user is setup."""
        await self._async_load()
        return user_id in self._users   # type: ignore

    async def async_is_supported(
            self, user_id: str, user_input: Dict[str, Any]) -> bool:
        """Return True if browser supported."""
        error = user_input.get(INPUT_FIELD_ERROR, None)
        return error not in [INPUT_ERROR_UNSUPPORTED, INPUT_ERROR_PROTOCOL]

    async def async_validate(
            self, user_id: str, user_input: Dict[str, Any]) -> bool:
        """Return True if validation passed."""
        await self._async_load()
        return await self.hass.async_add_executor_job(
            self._validate_webauthn,
            user_id,
            user_input.get(INPUT_FIELD_TOKEN, '')
        )

    def _validate_webauthn(self, user_id: str, token: str) -> bool:
        """Validate token."""
        if not token:
            return False

        credentials_encoded = self._users.get(user_id, None)
        if credentials_encoded is None:
            return False

        credential_id, client_data, auth_data, signature \
            = _get_validate_data(token)
        credentials = _decode_credentials(credentials_encoded)

        try:
            self._server.authenticate_complete(
                credentials,
                credential_id,
                self._challenge,
                client_data,
                auth_data,
                signature
            )
            return True
        except Exception:  # pylint: disable=broad-except
            return False

    async def async_get_login_mfa_additional_data(self, user_id: str) -> dict:
        """Setup additional data for client."""
        await self._async_load()

        credentials_encoded = self._users.get(user_id, None)
        if credentials_encoded is None:
            return {}

        credentials = _decode_credentials(credentials_encoded)
        self._server = _create_server(self.hass)
        auth_data = self._server.authenticate_begin(credentials)
        self._challenge = auth_data['publicKey']['challenge']

        return {
            'options': _encode_bytes_to_string(auth_data)
        }


class WebAuthnSetupFlow(SetupFlow):
    """Handler for the setup flow."""
    def __init__(self, auth_module: WebAuthnAuthModule,
                 setup_schema: vol.Schema,
                 user: User, credentials: list) -> None:
        """Initialize the setup flow."""
        super().__init__(auth_module, setup_schema, user.id)
        self._auth_module = auth_module  # type: WebAuthnAuthModule
        self._user = user  # type: User
        self._server = _create_server(auth_module.hass)
        self._challenge = None  # type: str
        self._credentials = credentials  # type: list
        self._invalid_mfa_times = 0  # type: int

    async def async_step_init(
            self, user_input: Optional[Dict[str, str]] = None) \
            -> Dict[str, Any]:
        """Handle steps of setup flow."""
        errors = {}  # type: Dict[str, str]
        user_error = None  # type: str
        token = None  # type: str

        if user_input:
            user_error = user_input.get(INPUT_FIELD_ERROR)
            token = user_input.get(INPUT_FIELD_TOKEN)

        if token:
            try:
                client_data, att_obj = _get_create_data(token)
                auth_data = self._server.register_complete(
                    self._challenge,
                    client_data,
                    att_obj
                )

                self._credentials.append(auth_data.credential_data)
                result = await self._auth_module.async_setup_user(
                    self._user_id, self._credentials)

                return self.async_create_entry(
                    title=self._auth_module.name,
                    data={'result': result}
                )
            except Exception:  # pylint: disable=broad-except
                return self.async_abort(reason='register_error')

        if user_error:
            if user_error != INPUT_ERROR_CREDENTIALS:
                return self.async_abort(reason=user_error)

            errors['base'] = user_error
            self._invalid_mfa_times += 1

            if self._invalid_mfa_times >= self._auth_module.MAX_RETRY_TIME:
                return self.async_abort(reason='too_many_retry')

        registration_data = self._server.register_begin({
            'id': self._user_id.encode('utf-8'),
            'name': self._user.name,
            'displayName': self._user.name
        }, self._credentials)

        self._challenge = registration_data['publicKey']['challenge']
        data = {
            'options': _encode_bytes_to_string(registration_data)
        }

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({}, extra=vol.ALLOW_EXTRA),
            data=data,
            errors=errors
        )
