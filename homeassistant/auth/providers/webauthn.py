"""Webauthn auth provider for Home Assistant."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import json
import logging
from typing import Any, cast

import voluptuous as vol
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidRegistrationResponse,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)

from homeassistant.auth.models import AuthFlowResult, User
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..models import Credentials
from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow

_LOGGER = logging.getLogger(__name__)


STORAGE_VERSION = 1
STORAGE_KEY = "auth_provider.webauthn"
AUTH_PROVIDER_TYPE = "webauthn"


CONF_RP_ID = "rp_id"
CONF_RP_NAME = "rp_name"
CONF_EXPECTED_ORIGIN = "expected_origin"


CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Required(CONF_RP_ID): str,
        vol.Required(CONF_EXPECTED_ORIGIN): str,
        vol.Optional(CONF_RP_NAME, default="Home Assistant"): str,
    },
    extra=vol.PREVENT_EXTRA,
)


class InvalidAuth(HomeAssistantError):
    """Raised when we encounter invalid authentication."""


class InvalidUser(HomeAssistantError):
    """Raised when invalid user is specified. Will not be raised when validating authentication."""


class InvalidChallenge(HomeAssistantError):
    """Raised when invalid challenge is specified."""


class CredentialsNotFound(HomeAssistantError):
    """Raised when credentials are not found."""


@callback
def async_get_provider(hass: HomeAssistant) -> WebauthnAuthProvider:
    """Get the provider."""
    for prv in hass.auth.auth_providers:
        if prv.type == AUTH_PROVIDER_TYPE:
            return cast(WebauthnAuthProvider, prv)

    raise RuntimeError("Provider not found")


class Data:
    """Hold the user data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the user data."""
        self.hass = hass
        self._store = Store[dict[str, dict[str, dict[str, str]]]](
            hass, STORAGE_VERSION, STORAGE_KEY, private=True, atomic_writes=True
        )
        self._data: dict[str, dict[str, dict[str, str]]] | None = None

    async def async_load(self) -> None:
        """Load stored data."""
        if (data := await self._store.async_load()) is None:
            data = cast(dict[str, dict[str, dict[str, str]]], {"users": {}})

        self._data = data

    @property
    def users(self) -> dict[str, dict[str, str]]:
        """Return the users."""
        assert self._data is not None
        return self._data["users"]

    async def async_save(self) -> None:
        """Save data."""
        if self._data is not None:
            await self._store.async_save(self._data)

    def add_challenge(self, user_id: str, challenge: str) -> None:
        """Add a challenge."""
        assert self._data is not None
        self.users[user_id].update({"challenge": challenge})

    def get_challenge(self, user_id: str) -> str:
        """Get a challenge."""
        try:
            return self.users[user_id]["challenge"]
        except KeyError as err:
            raise InvalidUser("Challenge not found") from err

    def add_registration(self, user_id: str, username: str, challenge: str) -> None:
        """Add a registration."""
        assert self._data is not None
        self.users[user_id] = {"username": username, "challenge": challenge}

    def get_user_id(self, username: str) -> str | None:
        """Get a user id."""
        for user_id, user in self.users.items():
            if user["username"] == username:
                return user_id
        return None

    def get_username(self, user: User) -> str:
        """Get a user name."""
        try:
            if user.id in self.users:
                return self.users[user.id]["username"]
            for cred in user.credentials:
                if cred.auth_provider_type == "homeassistant":
                    return cast(str, cred.data["username"])
        except KeyError as err:
            raise InvalidUser("Username not found") from err
        else:
            return cast(str, user.name)


@AUTH_PROVIDERS.register(AUTH_PROVIDER_TYPE)
class WebauthnAuthProvider(AuthProvider):
    """Webauthn auth provider for Home Assistant."""

    DEFAULT_TITLE = "Home Assistant Passkeys"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize an Home Assistant auth provider."""
        super().__init__(*args, **kwargs)
        self.data: Data | None = None
        self._init_lock = asyncio.Lock()

    async def async_initialize(self) -> None:
        """Initialize the auth provider."""
        async with self._init_lock:
            if self.data is not None:
                return

            data = Data(self.hass)
            await data.async_load()
            self.data = data

    @property
    def rp_id(self) -> str:
        """Return the rp_id."""
        return cast(str, self.config[CONF_RP_ID])

    @property
    def rp_name(self) -> str:
        """Return the rp_name."""
        return cast(str, self.config[CONF_RP_NAME])

    @property
    def expected_origin(self) -> str:
        """Return the expected_origin."""
        return cast(str, self.config[CONF_EXPECTED_ORIGIN])

    @property
    def support_mfa(self) -> bool:
        """Webauthn auth provider does not support MFA."""
        return False

    async def async_generate_registration_options(self, user: User) -> Any:
        """Generate registration options."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        username = self.data.get_username(user)
        if username is None:
            raise InvalidUser
        options = generate_registration_options(
            rp_id=self.rp_id,
            rp_name=self.rp_name,
            user_id=bytes.fromhex(user.id),
            user_name=username,
            user_display_name=user.name,
            exclude_credentials=[
                PublicKeyCredentialDescriptor(base64url_to_bytes(cred.data["id"]))
                for cred in user.credentials
                if cred.auth_provider_type == AUTH_PROVIDER_TYPE
            ],
            authenticator_selection=AuthenticatorSelectionCriteria(
                user_verification=UserVerificationRequirement.REQUIRED
            ),
            supported_pub_key_algs=[
                COSEAlgorithmIdentifier.ECDSA_SHA_256,
                COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
            ],
        )

        await self.async_add_registration(
            user.id, username, bytes_to_base64url(options.challenge)
        )
        return json.loads(options_to_json(options))

    async def async_validate_registration(
        self, user: User, credentials: dict[str, str]
    ) -> None:
        """Validate webauthn registration."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        expected_challenge: str = self.data.get_challenge(user.id)
        username: str = self.data.get_username(user)

        try:
            verification = verify_registration_response(
                credential=credentials,
                expected_challenge=base64url_to_bytes(expected_challenge),
                expected_origin=self.expected_origin,
                expected_rp_id=self.rp_id,
                require_user_verification=True,
            )

            credentials_data = {
                "id": bytes_to_base64url(verification.credential_id),
                "username": username,
                "public_key": bytes_to_base64url(verification.credential_public_key),
                "sign_count": str(verification.sign_count),
                "name": "Home Assistant Passkey",
                "created_at": dt_util.utcnow().isoformat(),
                "last_used_at": dt_util.utcnow().isoformat(),
            }
            _credentials = self.async_create_credentials(credentials_data)
            await self.store.async_link_user(user, _credentials)
        except InvalidRegistrationResponse as err:
            _LOGGER.error("Error registering credential: %s", err)
            raise InvalidAuth(str(err)) from err

    async def async_add_registration(
        self, user_id: str, username: str, challenge: str
    ) -> None:
        """Call add_registration on data."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        self.data.add_registration(user_id, username, challenge)
        await self.data.async_save()

    async def async_add_challenge(self, user_id: str, challenge: str) -> None:
        """Call add_challenge on data."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        await self.hass.async_add_executor_job(
            self.data.add_challenge, user_id, challenge
        )
        await self.data.async_save()

    async def async_list_passkeys(self, user: User) -> list[dict[str, str]]:
        """List all passkeys."""
        return [
            {
                "id": credential.data["id"],
                "credential_id": credential.id,
                "name": credential.data["name"],
                "created_at": credential.data["created_at"],
                "last_used_at": credential.data["last_used_at"],
            }
            for credential in user.credentials
            if credential.auth_provider_type == AUTH_PROVIDER_TYPE
        ]

    async def async_delete_passkey(self, user: User, credential_id: str) -> None:
        """Delete a passkey."""
        for credential in user.credentials:
            if (
                credential.id == credential_id
                and credential.auth_provider_type == AUTH_PROVIDER_TYPE
            ):
                return await self.store.async_remove_credentials(credential)
        raise CredentialsNotFound("Credential not found")

    async def async_update_passkey(
        self, user: User, credential_id: str, name: str
    ) -> None:
        """Update a passkey name."""
        for credential in user.credentials:
            if (
                credential.id == credential_id
                and credential.auth_provider_type == AUTH_PROVIDER_TYPE
            ):
                credential.data["name"] = name
                return
        raise CredentialsNotFound("Credential not found")

    async def async_login_flow(self, context: dict[str, Any] | None) -> LoginFlow:
        """Return a flow to login."""
        return WebauthnLoginFlow(self)

    async def async_add_auth(self, user: User, credential: dict[str, str]) -> bool:
        """Validate webauthn registration."""
        await self.async_validate_registration(user, credential)
        return True

    async def async_generate_authentication_options(self, user: User) -> Any:
        """Generate authentication options."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        options = generate_authentication_options(
            rp_id=self.rp_id,
            allow_credentials=[
                PublicKeyCredentialDescriptor(base64url_to_bytes(cred.data["id"]))
                for cred in user.credentials
                if cred.auth_provider_type == AUTH_PROVIDER_TYPE
            ],
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        await self.async_add_challenge(user.id, bytes_to_base64url(options.challenge))
        return json.loads(options_to_json(options))

    async def async_validate_authentication(
        self, user: User, credentials: dict[str, str]
    ) -> None:
        """Validate webauthn authentication."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        try:
            expected_challenge = self.data.get_challenge(user.id)
            user_credentials = [
                cred
                for cred in user.credentials
                if cred.auth_provider_type == AUTH_PROVIDER_TYPE
                and cred.data.get("id") == credentials.get("id")
            ]
            if not user_credentials:
                raise InvalidUser("No credentials for user")
            user_credential = user_credentials[0]
            if expected_challenge is None:
                raise InvalidUser("No challenge for user")
            verification = verify_authentication_response(
                credential=credentials,
                credential_public_key=base64url_to_bytes(
                    user_credential.data["public_key"]
                ),
                credential_current_sign_count=int(user_credential.data["sign_count"]),
                expected_challenge=base64url_to_bytes(expected_challenge),
                expected_origin=self.expected_origin,
                expected_rp_id=self.rp_id,
            )
            user_credential.data.update(
                {
                    "sign_count": str(verification.new_sign_count),
                    "last_used_at": dt_util.utcnow().isoformat(),
                }
            )
        except InvalidAuthenticationResponse as err:
            _LOGGER.error("Error authenticating credential: %s", err)
            raise InvalidChallenge from err

    async def async_login(self, username: str) -> tuple[User, Any]:
        """Validate a username."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        user_id = self.data.get_user_id(username)
        if user_id is None:
            raise InvalidUser
        user = await self.store.async_get_user(user_id)
        if user is None:
            raise InvalidUser
        return user, await self.async_generate_authentication_options(user)

    async def async_get_or_create_credentials(
        self, flow_result: Mapping[str, Any]
    ) -> Credentials:
        """Get credentials based on the flow result."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        auth_credential_id = flow_result.get("authentication_credential", {}).get("id")
        if auth_credential_id is None:
            raise InvalidAuth

        for credential in await self.async_credentials():
            if credential.data.get("id") == auth_credential_id:
                return credential

        raise InvalidUser


class WebauthnLoginFlow(LoginFlow):
    """Handler for the login flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> AuthFlowResult:
        """Handle the step of the form."""
        errors = {}
        if user_input is not None:
            try:
                self.user, options = await cast(
                    WebauthnAuthProvider, self._auth_provider
                ).async_login(user_input["username"])
                options_schema = vol.Schema({}, extra=vol.ALLOW_EXTRA)
                return self.async_show_form(
                    step_id="challenge",
                    data_schema=options_schema,
                    description_placeholders={"webauthn_options": options},
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidUser:
                errors["base"] = "invalid_user"

            if not errors:
                return await self.async_finish(user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_challenge(
        self, user_input: dict[str, Any] | None = None
    ) -> AuthFlowResult | None:
        """Handle the step of the form."""
        errors = {}

        if user_input is not None:
            try:
                await cast(
                    WebauthnAuthProvider, self._auth_provider
                ).async_validate_authentication(
                    cast(User, self.user), user_input["authentication_credential"]
                )
            except InvalidUser:
                errors["base"] = "invalid_user"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidChallenge:
                errors["base"] = "invalid_challenge"

            if not errors:
                return await self.async_finish(user_input)
        else:
            errors["base"] = "invalid_auth"
        return self.async_show_form(
            step_id="challenge",
            data_schema=vol.Schema(
                {
                    vol.Required("authentication_credential"): dict,
                }
            ),
            errors=errors,
        )
