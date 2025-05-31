"""Config flow for the Evohome integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import TYPE_CHECKING, Any, Final, NotRequired, TypedDict

import evohomeasync2 as ec2
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.storage import Store

from .const import (
    CONF_HIGH_PRECISION,
    CONF_LOCATION_IDX,
    DEFAULT_HIGH_PRECISION,
    DEFAULT_HIGH_PRECISION_LEGACY,
    DEFAULT_LOCATION_IDX,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MINIMUM_SCAN_INTERVAL,
    STORAGE_KEY,
    STORAGE_VER,
    SZ_TOKEN_DATA,
)
from .storage import EvoTokenDataT, TokenManager

if TYPE_CHECKING:
    from .coordinator import EvoDataUpdateCoordinator  # circular import


DEFAULT_OPTIONS: Final[EvoOptionDataT] = {
    CONF_HIGH_PRECISION: DEFAULT_HIGH_PRECISION,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}


_LOGGER = logging.getLogger(__name__.rsplit(".", 1)[0])


class EvoConfigDataT(TypedDict):
    """Evohome's configuration dict as stored in a config entry."""

    username: str
    password: str
    location_idx: int
    token_data: NotRequired[EvoTokenDataT]


class EvoOptionDataT(TypedDict):
    """Evohome's options dict as stored in a config entry."""

    scan_interval: int
    high_precision: NotRequired[bool]


class EvoRuntimeDataT(TypedDict):
    """Evohome's runtime data dict as stored in a config entry."""

    coordinator: EvoDataUpdateCoordinator
    token_manager: TokenManager


class EvoConfigFileDictT(TypedDict):
    """Evohome's config dict as stored in configuration.yaml (after CONFIG_SCHEMA)."""

    username: str
    password: str
    location_idx: int
    scan_interval: timedelta


class _TokenStoreT(TypedDict):
    """Evohome's token cache as stored in local storage (to be deprecated)."""

    username: NotRequired[str]  # in the store's schema, is required
    refresh_token: str
    access_token: str
    access_token_expires: str  # dt.isoformat(), TZ-aware
    session_id: NotRequired[str]
    session_id_expires: NotRequired[str]  # dt.isoformat(), TZ-aware


class EvoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Evohome."""

    _client: ec2.EvohomeClient

    def __init__(self) -> None:
        """Initialize a config flow handler for Evohome."""

        self._username: str | None = None  # username.lower() is used as the unique_id
        self._password: str | None = None
        self._location_idx: int | None = None
        self._token_data: EvoTokenDataT | None = None

        self._num_locations: int | None = None

        self._options: EvoOptionDataT = DEFAULT_OPTIONS

    async def async_step_import(self, config: EvoConfigFileDictT) -> ConfigFlowResult:
        """Handle a flow initiated by import from a configuration file.

        Will abort if the unique_id (username) is already configured.
        """

        # for import, assume the user credentials/location index are valid
        await self.async_set_unique_id(config[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()  # dont import a config if already exists

        self._username = config[CONF_USERNAME]
        self._password = config[CONF_PASSWORD]
        self._location_idx = config[CONF_LOCATION_IDX]

        # leverage any cached tokens by importing them into the config entry
        store: Store[_TokenStoreT] = Store(self.hass, STORAGE_VER, STORAGE_KEY)
        cache: _TokenStoreT | None = await store.async_load()

        await store.async_remove()

        if cache and cache.pop(CONF_USERNAME) == self._username:
            self._token_data = cache

        # a timedelta is not serializable, so convert to seconds
        self._options[CONF_SCAN_INTERVAL] = config[CONF_SCAN_INTERVAL].seconds

        # before config flow, high_precision was implicitly enabled
        self._options[CONF_HIGH_PRECISION] = DEFAULT_HIGH_PRECISION_LEGACY

        return await self._update_or_create_entry()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle the reauth step after a ConfigEntryAuthFailed."""

        self._username = entry_data[CONF_USERNAME]
        self._location_idx = entry_data[CONF_LOCATION_IDX]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauth step (username/password)."""
        # self._get_reauth_entry()

        assert self._username is not None  # mypy

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._client = await self._test_credentials(
                    self._username, user_input[CONF_PASSWORD]
                )

            except (ConfigEntryAuthFailed, ConfigEntryNotReady) as err:
                if str(err) not in ("rate_exceeded", "cannot_connect", "invalid_auth"):
                    raise  # pragma: no cover
                errors["base"] = str(err)

            else:
                self._password = user_input[CONF_PASSWORD]
                return await self._update_or_create_entry()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD,
                        autocomplete="current-password",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=data_schema, errors=errors
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step (username/password)."""

        errors: dict[str, str] = {}

        if user_input is not None:
            # username is needed in  schema, and_save_token_data callback
            self._username = user_input[CONF_USERNAME]

            assert self._username is not None  # mypy

            await self.async_set_unique_id(self._username.lower())

            try:
                # leverage the following method to avoid unnecessary I/O
                self._abort_if_unique_id_configured(error="already_configured_account")

                self._client = await self._test_credentials(
                    self._username,
                    user_input[CONF_PASSWORD],
                )

                self._num_locations = await self._test_installation(self._client)

            except AbortFlow as err:
                # don't abort; just inform the user to use a different account
                errors["base"] = str(err.reason)

            except (ConfigEntryAuthFailed, ConfigEntryNotReady) as err:
                if str(err) not in ("rate_exceeded", "cannot_connect", "invalid_auth"):
                    raise  # pragma: no cover
                errors["base"] = str(err)

            else:
                self._password = user_input[CONF_PASSWORD]
                return await self.async_step_location()

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=self._username,
                ): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.EMAIL,
                        autocomplete="email",
                    )
                ),
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD,
                        autocomplete="current-password",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the second/final step (location index)."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self._location_idx = int(user_input[CONF_LOCATION_IDX])
            return await self._update_or_create_entry()

        assert self._num_locations is not None  # mypy

        data_schema = self._location_idx_schema(
            DEFAULT_LOCATION_IDX,
            self._num_locations,
        )

        return self.async_show_form(
            step_id="location",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure step (location index)."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self._location_idx = int(user_input[CONF_LOCATION_IDX])
            return await self._update_or_create_entry()

        config_entry = self._get_reconfigure_entry()

        config: EvoConfigDataT = config_entry.data  # type: ignore[assignment]
        self._username = config[CONF_USERNAME]
        self._password = config[CONF_PASSWORD]
        self._location_idx = config[CONF_LOCATION_IDX]

        runtime_data: EvoRuntimeDataT = config_entry.runtime_data
        self._num_locations = len(runtime_data["coordinator"].client.locations)

        data_schema = self._location_idx_schema(
            self._location_idx,
            self._num_locations,
        )

        return self.async_show_form(
            step_id="reconfigure", data_schema=data_schema, errors=errors
        )

    async def _test_credentials(
        self, username: str, password: str
    ) -> ec2.EvohomeClient:
        """Validate the user credentials and return a client."""

        token_manager = TokenManager(
            username,
            password,
            async_get_clientsession(self.hass),
            cache_loader=self._load_token_data,
            cache_saver=self._save_token_data,
            logger=_LOGGER,
        )

        # fetch a new access token from the vendor (i.e. not from the cache)
        try:
            await token_manager.get_access_token()

        except ec2.BadUserCredentialsError as err:
            _LOGGER.warning("Invalid credentials: %s", err)
            raise ConfigEntryAuthFailed("invalid_auth") from err

        except ec2.AuthenticationFailedError as err:
            _LOGGER.warning("Authentication failed: %s", err)
            if err.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise ConfigEntryNotReady("rate_exceeded") from err
            raise ConfigEntryNotReady("cannot_connect") from err

        return ec2.EvohomeClient(token_manager)

    async def _test_installation(self, client: ec2.EvohomeClient) -> int:
        """Retrieve the user installation and return the number of locations."""

        try:
            await client.update(dont_update_status=True)  # ? raise ec2.EvohomeError:

        except ec2.ApiRequestFailedError as err:
            _LOGGER.warning("Request failed: %s", err)
            if err.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise ConfigEntryNotReady("rate_exceeded") from err
            raise ConfigEntryNotReady("cannot_connect") from err

        return len(client.locations)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> EvoOptionsFlowHandler:
        """Define the options flow for Evohome."""
        return EvoOptionsFlowHandler(config_entry)

    async def _load_token_data(self, client_id: str) -> EvoTokenDataT | None:
        """Return token data as from an empty cache."""
        return None  # will force user credentials to be validated

    async def _save_token_data(self, client_id: str, token_data: EvoTokenDataT) -> None:
        """Save the token data to the config entry, so it can be used later."""

        if client_id == self._username:
            self._token_data = token_data

    async def _update_or_create_entry(self) -> ConfigFlowResult:
        """Create the config entry for this account, or update an existing entry."""

        assert self._username is not None  # mypy
        assert self._password is not None  # mypy
        assert self._location_idx is not None  # mypy

        config: EvoConfigDataT = {
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
            CONF_LOCATION_IDX: self._location_idx,
        }
        if self._token_data is not None:
            config.update({SZ_TOKEN_DATA: self._token_data})

        # from step_reauth or step_reconfigure
        #  - self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE)
        if config_entry := await self.async_set_unique_id(
            self._username.lower(),
        ):
            # preserve the existing token cache (if there isn't a new one)
            return self.async_update_reload_and_abort(
                config_entry,
                data_updates={k: v for k, v in config.items() if k != CONF_USERNAME},
            )

        # from step_user or step_import, retain any token cache
        return self.async_create_entry(
            title="Evohome",
            data=config,
            options=self._options,
        )

    def _location_idx_schema(
        self,
        location_idx: int,
        num_locations: int,
    ) -> vol.Schema:
        """Return a location index schema."""

        return vol.Schema(
            {
                vol.Required(CONF_LOCATION_IDX, default=location_idx): vol.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            max=num_locations - 1,
                            min=0,
                            step=1,
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                ),
            }
        )

    def _user_credentials_schema(
        self,
        username: str | None,
    ) -> vol.Schema:
        """Return a user credentials schema."""

        return vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=username,
                ): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.EMAIL,
                        autocomplete="email",
                    )
                )
            }
        ).extend(self._user_password_schema())

    def _user_password_schema(self) -> vol.Schema:
        """Return a user password schema."""

        return vol.Schema(
            {
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD,
                        autocomplete="current-password",
                    )
                ),
            }
        )


class EvoOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Evohome."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize an options flow handler for Evohome."""

        self._options: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the first step of options flow.

        Provides responsible default values for high_precision and scan_interval.
        """

        errors: dict[str, str] = {}

        self._options = dict(self.config_entry.options)

        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="Evohome", data=self._options)

        # the options schema is built to encourage a responsible configuration
        # legacy settings, from an imported configuration, are respected

        # suggest the previous behaviour
        default_high_precision = self._options[CONF_HIGH_PRECISION]

        # suggest a default of 300 (not 180) secs, unless previously set higher
        default_scan_interval = max(
            (DEFAULT_SCAN_INTERVAL, self._options[CONF_SCAN_INTERVAL])
        )

        # enforce a minimum of 180 (not 60) secs, unless previously set lower
        minimum_scan_interval = min(
            (MINIMUM_SCAN_INTERVAL, self._options[CONF_SCAN_INTERVAL])
        )

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_HIGH_PRECISION,
                    default=default_high_precision,
                ): BooleanSelector(),
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=default_scan_interval,
                ): vol.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            max=900,
                            min=minimum_scan_interval,
                            step=15,
                            mode=NumberSelectorMode.SLIDER,
                        ),
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )
