"""Config flow for the Evohome integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any, Final, NotRequired, TypedDict

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

DEFAULT_OPTIONS: Final = {
    CONF_HIGH_PRECISION: DEFAULT_HIGH_PRECISION,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}


_LOGGER = logging.getLogger(__name__.rsplit(".", 1)[0])


class EvoConfigDataT(TypedDict):
    """Evohome's configuration dict as stored in a config entry."""

    username: str
    password: NotRequired[str]
    location_idx: NotRequired[int]
    token_data: NotRequired[EvoTokenDataT]


class EvoOptionDataT(TypedDict):
    """Evohome's options dict as stored in a config entry."""

    scan_interval: int
    high_precision: NotRequired[bool]


class EvoRuntimeDataT(TypedDict):
    """Evohome's runtime data dict as stored in a config entry."""

    coordinator: str
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

    _token_manager: TokenManager
    _client: ec2.EvohomeClient

    def __init__(self) -> None:
        """Initialize a config flow handler for Evohome."""

        self._config: EvoConfigDataT = {}  # type: ignore[typeddict-item]
        self._options: dict[str, Any] = DEFAULT_OPTIONS
        self._token_data: EvoTokenDataT | None = None

    async def async_step_import(self, config: EvoConfigFileDictT) -> ConfigFlowResult:
        """Handle a flow initiated by import from a configuration file.

        Will abort if the unique_id (username) is already configured.
        """

        # for import, assume the user credentials/location index are valid
        await self.async_set_unique_id(config[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()  # dont import a config if already exists

        self._config = {
            CONF_USERNAME: config[CONF_USERNAME],
            CONF_PASSWORD: config[CONF_PASSWORD],
            CONF_LOCATION_IDX: config[CONF_LOCATION_IDX],
        }

        # leverage any cached tokens by importing them into the config entry
        store: Store[_TokenStoreT] = Store(self.hass, STORAGE_VER, STORAGE_KEY)
        cache: _TokenStoreT | None = await store.async_load()

        await store.async_remove()

        if cache and cache.pop(CONF_USERNAME) == config[CONF_USERNAME]:
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

        self._config = {
            CONF_USERNAME: entry_data[CONF_USERNAME],
            CONF_LOCATION_IDX: entry_data[CONF_LOCATION_IDX],
        }

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauth step (username/password)."""

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._token_manager = await self._test_credentials(
                    self._config[CONF_USERNAME], user_input[CONF_PASSWORD]
                )

            except (ConfigEntryAuthFailed, ConfigEntryNotReady) as err:
                if str(err) not in ("rate_exceeded", "cannot_connect", "invalid_auth"):
                    raise  # pragma: no cover
                errors["base"] = str(err)

            else:
                self._config[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                return await self._update_or_create_entry()

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_PASSWORD,
                ): TextSelector(
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
            # store username now, as needed in our _save_token_data callback
            self._config[CONF_USERNAME] = user_input[CONF_USERNAME]

            await self.async_set_unique_id(self._config[CONF_USERNAME].lower())

            try:
                self._abort_if_unique_id_configured()  # to avoid unnecessary I/O

                self._token_manager = await self._test_credentials(
                    self._config[CONF_USERNAME], user_input[CONF_PASSWORD]
                )

            except AbortFlow as err:
                errors["base"] = str(err.reason)  # usually: 'already_configured'

            except (ConfigEntryAuthFailed, ConfigEntryNotReady) as err:
                if str(err) not in ("rate_exceeded", "cannot_connect", "invalid_auth"):
                    raise  # pragma: no cover
                errors["base"] = str(err)

            else:
                self._config[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                return await self.async_step_location()

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=self._config.get(CONF_USERNAME),
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

    async def _test_credentials(self, username: str, password: str) -> TokenManager:
        """Validate the user credentials (that authentication is successful).

        Requires self._config[CONF_USERNAME] for the _save_token_data callback.
        """

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

        return token_manager

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the second/final step (location index)."""

        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_LOCATION_IDX] = int(user_input[CONF_LOCATION_IDX])

            try:
                self._client = await self._test_location_idx(
                    self._token_manager, user_input[CONF_LOCATION_IDX]
                )

            except (ConfigEntryAuthFailed, ConfigEntryNotReady) as err:
                if str(err) not in ("bad_location", "cannot_connect"):
                    raise  # pragma: no cover
                errors["base"] = str(err)

            else:
                self._config[CONF_LOCATION_IDX] = user_input[CONF_LOCATION_IDX]
                return await self._update_or_create_entry()

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOCATION_IDX,
                    default=DEFAULT_LOCATION_IDX,
                ): vol.All(
                    vol.Coerce(int),
                    NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="location", data_schema=data_schema, errors=errors
        )

    async def _test_location_idx(
        self, token_manager: TokenManager, location_idx: int
    ) -> ec2.EvohomeClient:
        """Validate the location_idx (that the location exists)."""

        client = ec2.EvohomeClient(token_manager)

        try:
            await client.update(dont_update_status=True)  # ? raise ec2.EvohomeError:

        except ec2.ApiRequestFailedError as err:
            _LOGGER.warning("Request failed: %s", err)
            raise ConfigEntryNotReady("cannot_connect") from err

        try:
            client.locations[location_idx]

        except IndexError as err:
            msg = (
                f"Config error: 'location_idx' = {location_idx}, "
                f"but the valid range is 0-{len(client.locations) - 1}"
            )
            _LOGGER.warning(msg)
            raise ConfigEntryNotReady("bad_location") from err

        return client

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

        if client_id == self._config[CONF_USERNAME]:
            self._token_data = token_data

    async def _update_or_create_entry(self) -> ConfigFlowResult:
        """Create the config entry for this account, or update an existing entry."""

        # from step_reauth: user/pass/locn, td
        if config_entry := await self.async_set_unique_id(
            self._config[CONF_USERNAME].lower()
        ):
            return self.async_update_reload_and_abort(
                config_entry,
                data=self._config | {SZ_TOKEN_DATA: self._token_data},
            )

        # from step_user or step_import: user/pass/locn, td & (default) options
        return self.async_create_entry(
            title="Evohome",
            data=self._config | {SZ_TOKEN_DATA: self._token_data},
            options=self._options,
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

        # suggest False, rather than previous behaviour, True
        default_high_precision = DEFAULT_HIGH_PRECISION

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
