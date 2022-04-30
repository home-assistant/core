"""
Fido2 WebAuthn authentication and registration module.

In order to use this module a correctly configured https reverse proxy and dns record must be set up.
this is because only https sites are allowed to use WebAuthn.
"""
from __future__ import annotations

import asyncio
import base64
import importlib
from typing import Any

import voluptuous as vol

from homeassistant.auth.models import User
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from . import (
    MULTI_FACTOR_AUTH_MODULE_SCHEMA,
    MULTI_FACTOR_AUTH_MODULES,
    MultiFactorAuthModule,
    SetupFlow,
)
from ..frontend_form_components import FrontendFormField
from ..frontend_form_components.field_fido2_login import Fido2LoginField
from ..frontend_form_components.field_fido2_register import Fido2RegisterField
from ..frontend_form_components.field_hidden import HiddenField

REQUIREMENTS = ["fido2==0.9.3"]

# origin: fido2 origin. this is required because external_url does not work. why?
# check_origin: if False, origin is not checked.
CONFIG_SCHEMA = MULTI_FACTOR_AUTH_MODULE_SCHEMA.extend(
    {"origin": str, "check_origin": bool}, extra=vol.PREVENT_EXTRA
)

STORAGE_VERSION = 1
STORAGE_KEY = "auth_module.fido2"
STORAGE_USERS = "users"
STORAGE_USER_ID = "user_id"
STORAGE_CREDENTIALS = "fido2_credentials"

INPUT_FIELD_REGISTRATION_ANS = "fido2_registration_answer"
INPUT_FIELD_LOGIN_ATTESTATION = "fido2_attestation"

registration_attestation_schema = vol.Schema(
    {
        vol.Required("result"): bool,
        vol.Required("clientData"): bytes,
        vol.Required("attestationObject"): bytes,
    }
)
login_decoded_schema = vol.Schema(
    {
        vol.Required("result"): bool,
        vol.Required("credentialId"): bytes,
        vol.Required("clientData"): bytes,
        vol.Required("authenticatorData"): bytes,
        vol.Required("signature"): bytes,
    }
)


class Fido2Wrapper:
    """Wrapper for fido2 server."""

    def __init__(
        self, hass: HomeAssistant, origin: str | None, check_origin: bool | None
    ) -> None:
        """
        Init method.

        This imports all the required modules and wraps utility methods.
        """
        self.fido = importlib.import_module("fido2")
        self.webauthn = importlib.import_module("fido2.webauthn")
        self.client = importlib.import_module("fido2.client")
        self.server = importlib.import_module("fido2.server")
        self.ctap2 = importlib.import_module("fido2.ctap2")
        self.rpid = importlib.import_module("fido2.rpid")

        self.rp_entity = self.fido.webauthn.PublicKeyCredentialRpEntity(
            origin if origin is not None else "localhost", "HomeAssistant fido2 mfa"
        )
        self.fido2server = self.fido.server.Fido2Server(
            self.rp_entity,
            verify_origin=lambda o: True
            if check_origin is None or not check_origin
            else self.rpid.verify_rp_id(self.rp_entity.id, o),
        )

    @staticmethod
    def _sanitize_object(data: Any) -> Any:
        """
        Sanitize data for CBOR encoding.

        This is needed because cbor does not support None.
        """
        if not isinstance(data, dict):
            return data

        keys = list(data.keys())
        if "_nones" in keys:
            raise ValueError()

        data["_nones"] = []

        for key in keys:
            if data[key] is None:
                data.pop(key)
                data["_nones"].append(key)
        return data

    @staticmethod
    def _desanitize_object(data: Any) -> Any:
        """
        Desanitize data from CBOR encoding.

        This is needed because cbor does not support None.
        """
        if not isinstance(data, dict):
            return data

        keys = list(data.keys())
        if "_nones" not in keys:
            return data

        for none_key in data["_nones"]:
            data[none_key] = None

        data.pop("_nones")
        return data

    def encode(self, data: dict) -> str:
        """Encode a dictionary data in a base64(CBOR) format."""
        return base64.b64encode(
            self.fido.cbor.encode(Fido2Wrapper._sanitize_object(data))
        ).decode()

    def decode(self, data: str) -> Any:
        """Take a base64(CBOR) encoded object and return the corresponding dict."""
        return Fido2Wrapper._desanitize_object(
            self.fido.cbor.decode(base64.b64decode(data))
        )

    def registration_begin(
        self, user_id: bytes, user_name: str | None, display_name: str | None
    ) -> tuple[Any, Any]:
        """
        Obtain the registration object and the state object.

        Those objects are used by WebAuthn to get the attestation from the registering user.
        """
        reg, state = self.fido2server.register_begin(
            {
                "id": user_id,
                "name": user_name if user_name is not None else "",
                "displayName": display_name if display_name is not None else "",
            },
            [],
            user_verification="discouraged",
            authenticator_attachment="cross-platform",
        )
        return reg, state

    def registration_finalize(self, state: Any, c_data: Any, a_obj: Any) -> Any:
        """Take an attestation and return the user credentials object."""
        client_data = self.client.ClientData(c_data)
        attestation_obj = self.ctap2.AttestationObject(a_obj)
        return self.fido2server.register_complete(
            state, client_data, attestation_obj
        ).credential_data

    def _map_credentials(self, creds: list[Any]) -> list:
        """Take a list of encoded credentials and return a list of instantiated objects."""
        return list(map(self.ctap2.AttestedCredentialData, creds))

    def auth_begin(self, credentials: list[Any]) -> tuple[Any, Any]:
        """Return the objects needed for authentication to be user with WebAuthn."""
        auth, state = self.fido2server.authenticate_begin(
            self._map_credentials(credentials)
        )
        return auth, state

    def auth_verify(
        self,
        credentials: list[Any],
        state: Any,
        credential_id: Any,
        c_data: Any,
        a_data: Any,
        signature: Any,
    ) -> bool:
        """Take the state and the signature, alongside client_data and auth_data and check the auth validity."""
        client_data = self.fido.client.ClientData(c_data)
        auth_data = self.fido.ctap2.AuthenticatorData(a_data)
        try:
            self.fido2server.authenticate_complete(
                state,
                self._map_credentials(credentials),
                credential_id,
                client_data,
                auth_data,
                signature,
            )
            return True
        except ValueError:
            return False


@MULTI_FACTOR_AUTH_MODULES.register("fido2")
class Fido2AuthModule(MultiFactorAuthModule):
    """Auth module validate FIDO2 protocol exchange."""

    DEFAULT_TITLE = "Fido2-WebAuthn auth verification"
    MAX_RETRY_TIME = 3

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the user data store."""
        super().__init__(hass, config)
        self._server = Fido2Wrapper(hass, config["origin"], config["check_origin"])
        self._users: dict[str, str] | None = None
        self._user_store = hass.helpers.storage.Store(
            STORAGE_VERSION, STORAGE_KEY, private=True, atomic_writes=True
        )
        self._init_lock = asyncio.Lock()

    def _get_credentials(self, user_id_filter: str | None = None) -> list:
        """Get all the user credentials."""
        credentials = []
        users = list(self._users.keys() if self._users is not None else [])
        for usr in users:
            if user_id_filter is None or usr in user_id_filter:
                credentials.append(self._server.decode(self._users[usr]))  # type: ignore[index]
        return credentials

    @property
    def input_schema(self) -> vol.Schema:
        """Validate login flow input data."""
        auth_data, state = self._server.auth_begin(self._get_credentials())
        return vol.Schema(
            {
                FrontendFormField(
                    vol.Required("auth_response"),
                    Fido2LoginField(),
                    auth_data=self._server.encode(auth_data),
                ): str,
                FrontendFormField(
                    vol.Required("state"),
                    HiddenField(),
                    default=self._server.encode(state),
                ): str,
            }
        )

    def _finalize_registration(
        self, user_id: str, state: Any, client_data: Any, attestation_obj: Any
    ) -> str:
        """
        Take the user attestation and return the credentials.

        Those credentials are encoded and save in the module data store.
        """
        auth_data = self._server.registration_finalize(
            state, client_data, attestation_obj
        )
        encoded_data = self._server.encode(auth_data)
        self._users[user_id] = encoded_data  # type: ignore[index]
        return encoded_data

    def _validate(
        self,
        user_id: str,
        state: Any,
        credentials_id: Any,
        client_data: Any,
        authenticator_data: Any,
        signature: Any,
    ) -> bool:
        """Check user login validity."""
        return self._server.auth_verify(
            self._get_credentials(user_id),
            state,
            credentials_id,
            client_data,
            authenticator_data,
            signature,
        )

    async def _async_load(self) -> None:
        """Load stored data."""
        async with self._init_lock:
            if self._users is not None:
                return

            if (data := await self._user_store.async_load()) is None:
                data = {STORAGE_USERS: {}}
            self._users = data.get(STORAGE_USERS, {})

    async def _async_save(self) -> None:
        """Save data."""
        await self._user_store.async_save({STORAGE_USERS: self._users})

    async def async_setup_flow(self, user_id: str) -> SetupFlow:
        """Return a data entry flow handler for setup module.

        Mfa module should extend SetupFlow
        """
        user = await self.hass.auth.async_get_user(user_id)
        assert user is not None
        return Fido2SetupFlow(self, user, self._server)

    async def async_setup_user(self, user_id: str, setup_data: Any) -> str:
        """Set up auth module for user."""
        if self._users is None:
            await self._async_load()

        result = await self.hass.async_add_executor_job(
            self._finalize_registration,
            user_id,
            setup_data.get("state"),
            setup_data.get("attestation")["clientData"],
            setup_data.get("attestation")["attestationObject"],
        )

        await self._async_save()
        return result

    async def async_depose_user(self, user_id: str) -> None:
        """Depose auth module for user."""
        if self._users is None:
            await self._async_load()

        if self._users.pop(user_id, None):  # type: ignore[union-attr]
            await self._async_save()

    async def async_is_user_setup(self, user_id: str) -> bool:
        """Return whether user is setup."""
        if self._users is None:
            await self._async_load()
        return user_id in self._users  # type: ignore[operator]

    async def async_validate(self, user_id: str, user_input: dict[str, Any]) -> bool:
        """Return True if validation passed."""
        if "state" in user_input.keys() and "auth_response" in user_input.keys():
            if self._users is None:
                await self._async_load()
            try:
                decoded = self._server.decode(user_input["auth_response"])
                decoded = login_decoded_schema(decoded)
                return await self.hass.async_add_executor_job(
                    self._validate,
                    user_id,
                    self._server.decode(user_input["state"]),
                    decoded["credentialId"],
                    decoded["clientData"],
                    decoded["authenticatorData"],
                    decoded["signature"],
                )
            except ValueError:
                return False
        return False


class Fido2SetupFlow(SetupFlow):
    """Handler for the setup flow."""

    def __init__(
        self, auth_module: Fido2AuthModule, user: User, server: Fido2Wrapper
    ) -> None:
        """Initialize the setup flow."""
        super().__init__(auth_module, vol.Schema({}), user.id)
        # to fix typing complaint
        self._auth_module: Fido2AuthModule = auth_module
        self._user = user
        self._server = server

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of setup flow.

        Return self.async_show_form(step_id='init') if user_input is None.
        Return self.async_create_entry(data={'result': result}) if finish.
        """

        if user_input:
            attestation_data = self._server.decode(user_input["attestation"])
            try:
                attestation_data = registration_attestation_schema(attestation_data)
                if attestation_data["result"]:
                    await self._auth_module.async_setup_user(
                        self._user.id,
                        {
                            "state": self._server.decode(user_input["state"]),
                            "attestation": attestation_data,
                        },
                    )
                    return self.async_create_entry(
                        title=self._auth_module.name, data={"result": "ok"}
                    )
                return self.async_abort(
                    reason=f"failure caused by "
                    f"{attestation_data['cause'] if 'cause' in attestation_data.keys() else 'unknown'}"
                )
            except ValueError as exception:
                return self.async_abort(reason=f"invalid data. {str(exception)}")

        reg_data, state = self._server.registration_begin(
            self._user.id.encode(), self._user.name, self._user.name
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    FrontendFormField(
                        vol.Required("attestation"),
                        Fido2RegisterField(),
                        registration_data=self._server.encode(reg_data),
                    ): str,
                    FrontendFormField(
                        vol.Required("state"),
                        HiddenField(),
                        default=self._server.encode(state),
                    ): str,
                }
            ),
            description_placeholders={},
        )
