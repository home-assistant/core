"""Config flow for the Seafile integration."""

from contextlib import suppress
import hashlib
from typing import Any, override
from uuid import uuid4

from aioseafile import (
    Library,
    Seafile,
    SeafileAuthenticationError,
    SeafileError,
    SeafileTwoFactorRequiredError,
)
import probatio
from yarl import URL

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_BACKUP,
    CONF_BACKUP_PATH,
    CONF_LIBRARIES,
    CONF_LIBRARY_ID,
    CONF_OTP,
    DEFAULT_BACKUP_PATH,
    DOMAIN,
    SUBENTRY_TYPE_LIBRARY,
)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        probatio.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
        ),
        probatio.Required(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
        probatio.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)

STEP_OTP_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_OTP): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="one-time-code")
        ),
    }
)


BACKUP_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_BACKUP, default=False): bool,
        probatio.Required(
            CONF_BACKUP_PATH, default=DEFAULT_BACKUP_PATH
        ): TextSelector(),
    }
)


def _backup_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return the backup settings, with the folder as an absolute path."""
    return {
        CONF_BACKUP: user_input[CONF_BACKUP],
        CONF_BACKUP_PATH: "/" + user_input[CONF_BACKUP_PATH].strip("/"),
    }


def _library_options(libraries: list[Library]) -> list[SelectOptionDict]:
    """Return the libraries that can be added, sorted by name."""
    return [
        SelectOptionDict(value=library.id, label=library.name)
        for library in sorted(libraries, key=lambda library: library.name.lower())
        # Encrypted libraries need their password for most operations.
        if not library.encrypted
    ]


class SeafileConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Seafile."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._user_input: dict[str, Any] = {}
        self._client: Seafile | None = None
        self._token: str | None = None
        self._libraries: list[Library] = []
        self._removed = False

    async def _async_login(
        self, errors: dict[str, str], otp: str | None = None
    ) -> ConfigFlowResult | None:
        """Log in and continue, or record an error and return None."""
        self._client = client = Seafile(
            self._user_input[CONF_URL],
            session=async_get_clientsession(
                self.hass, verify_ssl=self._user_input[CONF_VERIFY_SSL]
            ),
        )
        try:
            self._token = await client.get_auth_token(
                self._user_input[CONF_USERNAME],
                self._user_input[CONF_PASSWORD],
                otp,
                # Registered as a device, so the user can see and revoke the token.
                device_id=hashlib.sha1(uuid4().bytes).hexdigest(),
                device_name=f"Home Assistant ({self.hass.config.location_name})",
            )
            if self._removed:
                # Cancelled while logging in, before there was a token to revoke.
                await self._async_revoke_token(client)
                return None
            account = await client.get_account_info()
            self._libraries = await client.get_libraries()
        except SeafileTwoFactorRequiredError:
            if otp is None:
                return await self.async_step_otp()
            errors["base"] = "invalid_otp"
        except SeafileAuthenticationError:
            errors["base"] = "invalid_auth"
        except SeafileError:
            await self._async_revoke_token(client)
            errors["base"] = "cannot_connect"
        else:
            # The account's internal user ID, which never changes; it is a
            # random virtual ID, except for the account created at server setup.
            await self.async_set_unique_id(account.email)
            self._abort_if_unique_id_configured()
            return await self.async_step_libraries()
        return None

    async def _async_revoke_token(self, client: Seafile) -> None:
        """Don't leave a token that won't be used on the server."""
        if self._token is None:
            return
        self._token = None
        with suppress(SeafileError):
            await client.logout_device()

    @callback
    @override
    def async_remove(self) -> None:
        """Revoke the token when the flow ends without creating the entry."""
        self._removed = True
        if self._token is not None and self._client is not None:
            self.hass.async_create_task(self._async_revoke_token(self._client))

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._user_input = user_input
            if result := await self._async_login(errors):
                return result
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the two-factor authentication code."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if result := await self._async_login(errors, user_input[CONF_OTP]):
                return result
        return self.async_show_form(
            step_id="otp", data_schema=STEP_OTP_DATA_SCHEMA, errors=errors
        )

    async def async_step_libraries(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick the libraries to add."""
        if user_input is not None:
            names = {library.id: library.name for library in self._libraries}
            token = self._token
            assert token is not None
            # The entry owns the token now, so async_remove must not revoke it.
            self._token = None
            return self.async_create_entry(
                title=f"{self._user_input[CONF_USERNAME]} ({URL(self._user_input[CONF_URL]).host})",
                data={
                    CONF_URL: self._user_input[CONF_URL],
                    CONF_TOKEN: token,
                    CONF_VERIFY_SSL: self._user_input[CONF_VERIFY_SSL],
                },
                subentries=[
                    {
                        "subentry_type": SUBENTRY_TYPE_LIBRARY,
                        "data": {
                            CONF_LIBRARY_ID: library_id,
                            CONF_BACKUP: False,
                            CONF_BACKUP_PATH: DEFAULT_BACKUP_PATH,
                        },
                        "title": names[library_id],
                        "unique_id": library_id,
                    }
                    for library_id in user_input[CONF_LIBRARIES]
                ],
            )
        return self.async_show_form(
            step_id="libraries",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(CONF_LIBRARIES, default=[]): SelectSelector(
                        SelectSelectorConfig(
                            options=_library_options(self._libraries), multiple=True
                        )
                    ),
                }
            ),
        )

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_LIBRARY: LibrarySubentryFlowHandler}


class LibrarySubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow to add or reconfigure a library."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._libraries: dict[str, Library] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Let the user pick a library and whether to store backups in it."""
        entry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            library_id = user_input[CONF_LIBRARY_ID]
            return self.async_create_entry(
                title=self._libraries[library_id].name,
                data={CONF_LIBRARY_ID: library_id, **_backup_data(user_input)},
                unique_id=library_id,
            )

        # Fetched here, as libraries created after setup aren't in the coordinator
        # data when the account has no library sensors to refresh it.
        try:
            libraries = await entry.runtime_data.client.get_libraries()
        except SeafileError:
            return self.async_abort(reason="cannot_connect")
        self._libraries = {library.id: library for library in libraries}

        configured = {
            subentry.unique_id
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LIBRARY)
        }
        options = [
            option
            for option in _library_options(libraries)
            if option["value"] not in configured
        ]
        if not options:
            return self.async_abort(reason="no_libraries")
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_LIBRARY_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
                    ),
                    **BACKUP_SCHEMA.schema,
                }
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change whether backups are stored in the library."""
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                data={**subentry.data, **_backup_data(user_input)},
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                BACKUP_SCHEMA, subentry.data
            ),
        )
