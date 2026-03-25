"""Config flow for Heiman Home Integration with OAuth2 authentication."""

import asyncio
import logging
import secrets
import traceback

from aiohttp import web
from aiohttp.hdrs import METH_GET
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.webhook import (
    async_generate_path as webhook_async_generate_path,
    async_register as webhook_async_register,
    async_unregister as webhook_async_unregister,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
import homeassistant.helpers.config_validation as cv

from .config_flow_enhanced import ConfigFlowEnhanced, HomeSelector
from .const import (
    AREA_NAME_RULE_HOME,
    AREA_NAME_RULE_HOME_ROOM,
    AREA_NAME_RULE_NONE,
    AREA_NAME_RULE_ROOM,
    CONF_AREA_NAME_RULE,
    CONF_DEVICES_CONFIG,
    CONF_TOKEN_EXPIRES_TS,
    DEFAULT_INTEGRATION_LANGUAGE,
    DEFAULT_REGION,
    DEFAULT_SECURE_ID,
    DEFAULT_SECURE_KEY,
    DOMAIN,
    INTEGRATION_LANGUAGES,
    OAUTH2_CLIENT_ID,
    OAUTH2_REDIRECT_URL,
    REGIONS,
    SECURE_ID,
    SECURE_KEY,
)
from .heiman_error import (
    HeimanAuthError,
    HeimanConfigError,
    HeimanError,
    HeimanErrorCode,
)
from .heiman_i18n import HeimanI18n
from .heiman_oauth import HeimanHttpClient, HeimanOauthClient
from .heiman_storage import HeimanStorage
from .web_pages import oauth_redirect_page

_LOGGER = logging.getLogger(__name__)


def _raise_config_error(
    message: str,
    error_code: HeimanErrorCode = HeimanErrorCode.CODE_CONFIG_INVALID_INPUT,
) -> None:
    """Raise a configuration error."""
    raise HeimanConfigError(message, error_code)


def _raise_auth_error(message: str) -> None:
    """Raise an authentication error."""
    raise HeimanAuthError(message)


def _raise_webhook_config_error(
    message: str,
    error_code: HeimanErrorCode = HeimanErrorCode.CODE_CONFIG_INVALID_INPUT,
) -> None:
    """Raise a webhook configuration error."""
    raise HeimanConfigError(message, error_code)


class HeimanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Heiman Home config flow with OAuth2."""

    VERSION = 1
    MINOR_VERSION = 1
    DEFAULT_AREA_NAME_RULE = AREA_NAME_RULE_ROOM

    def __init__(self) -> None:
        """Initialize config flow."""
        self._main_loop = asyncio.get_running_loop()
        self._storage: HeimanStorage | None = None
        self._i18n: HeimanI18n | None = None

        self._oauth_client: HeimanOauthClient | None = None
        self._http_client: HeimanHttpClient | None = None

        self._virtual_did = ""
        self._cloud_server = DEFAULT_REGION
        self._integration_language = DEFAULT_INTEGRATION_LANGUAGE
        self._secure_id = DEFAULT_SECURE_ID
        self._secure_key = DEFAULT_SECURE_KEY

        self._auth_info: dict = {}
        self._user_info: dict = {}
        self._homes: dict = {}
        self._devices: dict = {}
        self._mqtt_info: dict = {}

        # Room name sync mode
        self._area_name_rule: str = self.DEFAULT_AREA_NAME_RULE
        # Device configs (name, area_id overrides)
        self._devices_config: dict = {}
        # Current device index for config step
        self._current_device_idx: int = 0
        # List of devices to configure
        self._devices_list: list = []

        self._oauth_redirect_url_full = ""
        self._oauth_auth_url = ""

        self._storage_path = ""
        self._fut_oauth_code: asyncio.Future | None = None
        self._task_oauth: asyncio.Task | None = None
        self._config_rc: str | None = None

        # Enhanced config flow components
        self._config_enhancer = ConfigFlowEnhanced()
        self._home_selector = HomeSelector()
        self._network_detect_results = []

    async def _cleanup_http_client(self) -> None:
        """Clean up the HTTP client."""
        if self._http_client:
            try:
                await self._http_client.deinit_async()
            except Exception as cleanup_err:  # noqa: BLE001
                _LOGGER.debug("Failed to cleanup HTTP client: %s", cleanup_err)
            self._http_client = None

    async def _cleanup_oauth_client(self) -> None:
        """Clean up the OAuth client."""
        if self._oauth_client:
            try:
                await self._oauth_client.deinit_async()
            except Exception as cleanup_err:  # noqa: BLE001
                _LOGGER.debug("Failed to cleanup OAuth client: %s", cleanup_err)
            self._oauth_client = None

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        self.hass.data.setdefault(DOMAIN, {})

        # Generate virtual device ID
        if not self._virtual_did:
            self._virtual_did = str(secrets.randbits(64))
            self.hass.data[DOMAIN][self._virtual_did] = {}

        # Set storage path
        if not self._storage_path:
            self._storage_path = self.hass.config.path(".storage", DOMAIN)

        # Initialize storage
        if not self._storage:
            self._storage = HeimanStorage(
                root_path=self._storage_path,
                loop=self._main_loop,
            )
            await self._storage.init_async()
            self.hass.data[DOMAIN]["storage"] = self._storage

        return await self.async_step_eula(user_input)

    async def async_step_eula(self, user_input: dict | None = None):
        """Handle EULA step."""
        if user_input:
            if user_input.get("eula", None) is True:
                return await self.async_step_auth_config()
            return await self.__show_eula_form("eula_not_agree")
        return await self.__show_eula_form("")

    async def __show_eula_form(self, reason: str):
        """Show EULA form."""
        return self.async_show_form(
            step_id="eula",
            data_schema=vol.Schema(
                {
                    vol.Required("eula", default=False): bool,
                },
            ),
            last_step=False,
            errors={"base": reason},
        )

    async def async_step_auth_config(self, user_input: dict | None = None):
        """Handle authentication configuration step."""
        if user_input:
            self._cloud_server = user_input.get("cloud_server", DEFAULT_REGION)
            self._integration_language = user_input.get(
                "integration_language",
                DEFAULT_INTEGRATION_LANGUAGE,
            )
            # Use fixed secure credentials
            self._secure_id = SECURE_ID
            self._secure_key = SECURE_KEY

            # Initialize i18n
            self._i18n = HeimanI18n(
                language=self._integration_language,
                loop=self._main_loop,
            )
            await self._i18n.init_async()

            # Generate OAuth redirect URL
            webhook_path = webhook_async_generate_path(webhook_id=self._virtual_did)
            self._oauth_redirect_url_full = (
                f"{user_input.get('oauth_redirect_url')}{webhook_path}"
            )

            return await self.async_step_oauth()

        return await self.__show_auth_config_form("")

    async def __show_auth_config_form(self, reason: str):
        """Show authentication configuration form."""
        # Generate default language from Home Assistant config
        default_language = self.hass.config.language
        if default_language not in INTEGRATION_LANGUAGES:
            if default_language.split("-", 1)[0] not in INTEGRATION_LANGUAGES:
                default_language = DEFAULT_INTEGRATION_LANGUAGE
            else:
                default_language = default_language.split("-", 1)[0]

        # Build cloud server options - only show enabled regions with friendly names
        cloud_server_options = {
            "eu": "Europe",  # Only enabled region
        }

        return self.async_show_form(
            step_id="auth_config",
            data_schema=vol.Schema(
                {
                    vol.Required("cloud_server", default=self._cloud_server): vol.In(
                        cloud_server_options,
                    ),
                    vol.Required(
                        "integration_language",
                        default=default_language,
                    ): vol.In(INTEGRATION_LANGUAGES),
                    vol.Required(
                        "oauth_redirect_url",
                        default=OAUTH2_REDIRECT_URL,
                    ): vol.In([OAUTH2_REDIRECT_URL]),
                },
            ),
            errors={"base": reason},
            last_step=False,
        )

    async def async_step_oauth(self, user_input: dict | None = None):
        """Handle OAuth2 authentication step."""
        try:
            # Initialize OAuth client
            if not self._oauth_client:
                region_config = REGIONS.get(self._cloud_server) or REGIONS.get(
                    DEFAULT_REGION,
                )

                _LOGGER.debug(">>> Initializing OAuth client")
                _LOGGER.debug(">>> Cloud server: %s", self._cloud_server)
                _LOGGER.debug(">>> Region config: %s", region_config)
                _LOGGER.debug(">>> Redirect URL: %s", self._oauth_redirect_url_full)

                self._oauth_client = HeimanOauthClient(
                    client_id=OAUTH2_CLIENT_ID,
                    redirect_url=self._oauth_redirect_url_full,
                    cloud_server=self._cloud_server,
                    region_config=region_config,
                    loop=self._main_loop,
                )

                self._oauth_auth_url = self._oauth_client.gen_auth_url(
                    redirect_url=self._oauth_redirect_url_full,
                )

                # Store OAuth state and i18n for webhook
                self.hass.data[DOMAIN][self._virtual_did]["oauth_state"] = (
                    self._oauth_client.state
                )
                self.hass.data[DOMAIN][self._virtual_did]["i18n"] = self._i18n

                _LOGGER.debug("OAuth2 auth URL: %s", self._oauth_auth_url)

                # Register webhook for OAuth callback
                webhook_async_unregister(self.hass, webhook_id=self._virtual_did)
                webhook_async_register(
                    self.hass,
                    domain=DOMAIN,
                    name="oauth redirect webhook",
                    webhook_id=self._virtual_did,
                    handler=_handle_oauth_webhook,
                    allowed_methods=(METH_GET,),
                )

                # Create future for OAuth code
                if "fut_oauth_code" not in self.hass.data[DOMAIN][self._virtual_did]:
                    self._fut_oauth_code = self._main_loop.create_future()
                    self.hass.data[DOMAIN][self._virtual_did]["fut_oauth_code"] = (
                        self._fut_oauth_code
                    )
                else:
                    self._fut_oauth_code = self.hass.data[DOMAIN][self._virtual_did][
                        "fut_oauth_code"
                    ]

            # Start OAuth check task
            if self._task_oauth is None:
                self._task_oauth = self.hass.async_create_task(
                    self.__check_oauth_async(),
                )

            # Check if task is complete
            if self._task_oauth.done():
                if error := self._task_oauth.exception():
                    _LOGGER.error("OAuth task exception: %s", error)
                    self._config_rc = str(error)
                    return self.async_show_progress_done(next_step_id="oauth_error")

                # Cleanup OAuth client
                if self._oauth_client:
                    await self._oauth_client.deinit_async()
                    self._oauth_client = None

                return self.async_show_progress_done(next_step_id="select_home")

            # Show progress while OAuth is in progress
            return self.async_show_progress(
                step_id="oauth",
                progress_action="oauth",
                description_placeholders={
                    "link_left": f'<a href="{self._oauth_auth_url}" target="_blank">',
                    "link_right": "</a>",
                    "link": self._oauth_auth_url,
                },
                progress_task=self._task_oauth,
            )

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("OAuth step error: %s, %s", err, traceback.format_exc())
            self._config_rc = str(err)
            return self.async_show_progress_done(next_step_id="oauth_error")

    async def __check_oauth_async(self) -> None:
        """Check OAuth callback and get token."""
        # Get OAuth code
        if not self._fut_oauth_code:
            raise HeimanConfigError("oauth_code_fut_error")

        oauth_code: str | None = await self._fut_oauth_code
        if not oauth_code:
            raise HeimanConfigError("oauth_code_error")

        _LOGGER.debug("=" * 80)
        _LOGGER.debug("OAuth Configuration Flow - Token Exchange Step")
        _LOGGER.debug("=" * 80)
        _LOGGER.debug(
            ">>> Received OAuth code (first 10 chars): %s...",
            oauth_code[:10],
        )
        _LOGGER.debug(">>> Cloud server: %s", self._cloud_server)
        _LOGGER.debug(
            ">>> OAuth client status: %s",
            "initialized" if self._oauth_client else "NOT initialized",
        )

        # Get access token
        try:
            if not self._oauth_client:
                _LOGGER.error("OAuth client not initialized!")
                _raise_config_error("oauth_client_error")

            _LOGGER.debug(">>> Calling get_access_token_async()")
            self._auth_info = await self._oauth_client.get_access_token_async(
                code=oauth_code,
            )

            _LOGGER.debug(">>> Access token obtained successfully")
            _LOGGER.debug(">>> Token expires at: %s", self._auth_info.get("expires_ts"))
            _LOGGER.debug(
                ">>> Access token (first 20 chars): %s...",
                self._auth_info["access_token"][:20],
            )

            # Initialize HTTP client
            region_config = REGIONS.get(self._cloud_server) or REGIONS.get(
                DEFAULT_REGION,
            )
            api_url = region_config.get("api_url", "")

            _LOGGER.debug(">>> Initializing HTTP client with API URL: %s", api_url)
            _LOGGER.debug(
                ">>> Access token (first 20 chars): %s...",
                self._auth_info["access_token"][:20],
            )

            if not self._http_client:
                self._http_client = HeimanHttpClient(
                    api_url=api_url,
                    client_id=OAUTH2_CLIENT_ID,
                    access_token=self._auth_info["access_token"],
                    loop=self._main_loop,
                )
            else:
                self._http_client.update_http_header(
                    access_token=self._auth_info["access_token"],
                )

            # Get user info
            _LOGGER.debug(">>> Calling get_user_info_async()")
            self._user_info = await self._http_client.get_user_info_async()
            _LOGGER.debug(">>> User info response: %s", self._user_info)
            self._user_id = self._user_info.get("id", "")

            if not self._user_id:
                _raise_auth_error("user_id_not_found")

            _LOGGER.debug("User info retrieved: %s", self._user_id)

        except HeimanError as err:
            _LOGGER.error("=" * 80)
            _LOGGER.error("OAuth token exchange failed!")
            _LOGGER.error("=" * 80)
            _LOGGER.error("Error type: %s", type(err).__name__)
            _LOGGER.error("Error message: %s", str(err))
            _LOGGER.error(
                "Error code: %s",
                err.error_code if hasattr(err, "error_code") else "N/A",
            )
            _LOGGER.error("Cloud server: %s", self._cloud_server)

            # Provide helpful troubleshooting hints
            if "404" in str(err):
                _LOGGER.error("")
                _LOGGER.error("TROUBLESHOOTING - 404 Error:")
                _LOGGER.error("  1. Check your region configuration (cn/eu/test)")
                _LOGGER.error("  2. Verify the token URL in region config")
                _LOGGER.error("  3. Ensure the OAuth2 token endpoint is correct")
                _LOGGER.error("  4. Check if the service is available in your region")
            elif "401" in str(err):
                _LOGGER.error("")
                _LOGGER.error("TROUBLESHOOTING - 401 Error:")
                _LOGGER.error("  1. Check your client_id configuration")
                _LOGGER.error("  2. Verify redirect_uri matches the OAuth app")
                _LOGGER.error("  3. Check if the authorization code is valid")
                _LOGGER.error("  4. Authorization codes expire quickly - try again")
            elif "connection" in str(err).lower():
                _LOGGER.error("")
                _LOGGER.error("TROUBLESHOOTING - Connection Error:")
                _LOGGER.error("  1. Check your network connection")
                _LOGGER.error("  2. Verify firewall settings")
                _LOGGER.error("  3. Check if the service is running")
                _LOGGER.error("  4. Try using VPN if in restricted region")

            _LOGGER.error("")
            _LOGGER.error("Full traceback:")
            _LOGGER.error("%s", traceback.format_exc())
            _LOGGER.error("=" * 80)

            # Cleanup HTTP client on error
            await self._cleanup_http_client()

            raise HeimanConfigError("get_token_error") from err
        except Exception as err:
            _LOGGER.error("=" * 80)
            _LOGGER.error("Unexpected error during OAuth token exchange!")
            _LOGGER.error("=" * 80)
            _LOGGER.error("Error type: %s", type(err).__name__)
            _LOGGER.error("Error message: %s", str(err))
            _LOGGER.error("Cloud server: %s", self._cloud_server)
            _LOGGER.error("")
            _LOGGER.error("Full traceback:")
            _LOGGER.error("%s", traceback.format_exc())
            _LOGGER.error("=" * 80)

            # Cleanup HTTP client on error
            await self._cleanup_http_client()

            raise HeimanConfigError("get_token_error") from err

        # Get home list
        try:
            _LOGGER.debug("=" * 80)
            _LOGGER.debug("Fetching homes from API")
            _LOGGER.debug("=" * 80)
            _LOGGER.debug(">>> User ID: %s", self._user_id)
            _LOGGER.debug(
                ">>> HTTP client status: %s",
                "initialized" if self._http_client else "NOT initialized",
            )

            homes_response = await self._http_client.get_homes_async(
                user_id=self._user_id,
            )
            _LOGGER.debug(
                ">>> Homes API response (first 500 chars): %s",
                str(homes_response)[:500],
            )

            # API returns {status, result: [...], message, timestamp}
            # get_homes_async returns result field which is a list
            homes = (
                homes_response.get("result", [])
                if isinstance(homes_response, dict)
                else homes_response
            )
            if not isinstance(homes, list):
                _LOGGER.warning(
                    "Unexpected homes format: %s, type: %s",
                    homes_response,
                    type(homes_response),
                )
                homes = []

            _LOGGER.info(">>> Received %s homes from API", len(homes))

            self._homes = {}
            for idx, home in enumerate(homes):
                home_id = home.get("homeId")
                if home_id:
                    self._homes[home_id] = {
                        "home_id": home_id,
                        "home_name": home.get("homeName", ""),
                        "device_count": home.get("deviceCount", 0),
                    }
                    _LOGGER.info(
                        ">>> Home %d: ID=%s, Name=%s, Devices=%s",
                        idx + 1,
                        home_id,
                        home.get("homeName", ""),
                        home.get("deviceCount", 0),
                    )

            _LOGGER.info("=" * 80)
            _LOGGER.info("Found %s homes for user %s", len(self._homes), self._user_id)
            _LOGGER.info("Homes dictionary: %s", self._homes)
            _LOGGER.info("=" * 80)

            if not self._homes:
                _LOGGER.error("No homes found in response!")
                _LOGGER.error("Response data: %s", homes_response)
                _raise_config_error("no_homes_found")

        except HeimanError as err:
            _LOGGER.error("=" * 80)
            _LOGGER.error("Failed to get homes!")
            _LOGGER.error("=" * 80)
            _LOGGER.error("Error type: %s", type(err).__name__)
            _LOGGER.error("Error message: %s", str(err))
            _LOGGER.error(
                "Error code: %s",
                err.error_code if hasattr(err, "error_code") else "N/A",
            )
            _LOGGER.error("")
            _LOGGER.error("Full traceback:")
            _LOGGER.error("%s", traceback.format_exc())
            _LOGGER.error("=" * 80)

            # Cleanup HTTP client on error
            await self._cleanup_http_client()

            raise
        except Exception as err:
            _LOGGER.error("=" * 80)
            _LOGGER.error("Unexpected error while getting homes!")
            _LOGGER.error("=" * 80)
            _LOGGER.error("Error type: %s", type(err).__name__)
            _LOGGER.error("Error message: %s", str(err))
            _LOGGER.error("")
            _LOGGER.error("Full traceback:")
            _LOGGER.error("%s", traceback.format_exc())
            _LOGGER.error("=" * 80)

            # Cleanup HTTP client on error
            await self._cleanup_http_client()

            raise HeimanConfigError("get_homes_error") from err

        # Set unique ID
        await self.async_set_unique_id(f"{self._cloud_server}_{self._user_id}")
        _LOGGER.info("Unique ID set: %s", f"{self._cloud_server}_{self._user_id}")

        # Check if already configured - if so, update it instead of aborting
        existing_entry = self.hass.config_entries.async_get_entry(self.unique_id)
        if existing_entry:
            _LOGGER.info(
                "Entry already exists with ID: %s, updating instead of creating new",
                existing_entry.entry_id,
            )
            self._update_entry_on_finish = existing_entry

        # Save auth info to storage
        if self._storage:
            await self._storage.save_async(
                domain="auth_info",
                name=self._user_id,
                data={
                    "auth_info": self._auth_info,
                    "user_info": self._user_info,
                },
            )

        # Unregister OAuth webhook
        webhook_async_unregister(self.hass, webhook_id=self._virtual_did)
        _LOGGER.debug("OAuth webhook unregistered")

        # Cleanup OAuth client only (HTTP client still needed for select_home step)
        await self._cleanup_oauth_client()

        # NOTE: HTTP client is NOT cleaned up here - it's still needed in async_step_select_home
        # It will be cleaned up when the config flow is done

    async def async_step_oauth_error(self, user_input=None):
        """Handle OAuth error step."""
        if self._config_rc is None:
            return await self.async_step_oauth()

        if self._config_rc.startswith("Flow aborted: "):
            raise AbortFlow(reason=self._config_rc.replace("Flow aborted: ", ""))

        error_reason = self._config_rc
        self._config_rc = None

        return self.async_show_form(
            step_id="oauth_error",
            data_schema=vol.Schema({}),
            last_step=False,
            errors={"base": error_reason},
        )

    async def async_step_select_home(self, user_input: dict | None = None):
        """Handle home selection step with room name sync mode."""
        _LOGGER.debug("=" * 80)
        _LOGGER.debug("async_step_select_home called")
        _LOGGER.debug("=" * 80)
        _LOGGER.debug("User input: %s", user_input)

        if user_input:
            selected_home_ids = user_input.get("home_ids", [])
            self._area_name_rule = user_input.get(
                "area_name_rule",
                self.DEFAULT_AREA_NAME_RULE,
            )

            _LOGGER.info("=" * 80)
            _LOGGER.info("Home selection step - User input received")
            _LOGGER.info("Selected home IDs: %s", selected_home_ids)
            _LOGGER.info("Area name rule: %s", self._area_name_rule)
            _LOGGER.info("Available homes: %s", self._homes)
            _LOGGER.info("=" * 80)

            if not selected_home_ids:
                _LOGGER.warning("No home selected")
                return self.async_show_form(
                    step_id="select_home",
                    data_schema=self.__get_home_selection_schema(),
                    last_step=False,
                    errors={"base": "no_home_selected"},
                )

            # Check HTTP client is initialized
            if not self._http_client:
                _LOGGER.error("HTTP client not initialized in async_step_select_home")
                raise HeimanConfigError("http_client_not_initialized")

            _LOGGER.debug("HTTP client is initialized")
            _LOGGER.debug("User ID: %s", self._user_id)
            _LOGGER.debug("Secure ID: %s", self._secure_id)

            # Get devices for all selected homes
            all_devices = {}
            total_device_count = 0

            for idx, home_id in enumerate(selected_home_ids):
                try:
                    _LOGGER.info("=" * 80)
                    _LOGGER.info(
                        "Fetching devices for home %d/%s: %s",
                        idx + 1,
                        len(selected_home_ids),
                        home_id,
                    )
                    _LOGGER.info("User ID: %s", self._user_id)
                    _LOGGER.info("Secure ID: %s", self._secure_id)
                    _LOGGER.info("=" * 80)

                    # Get home info for room mapping
                    home_info = self._homes.get(home_id, {})
                    home_name = home_info.get("home_name", "")

                    mqtt_info = await self._http_client.get_devices_async(
                        home_id=home_id,
                        user_id=self._user_id,
                        secure_id=self._secure_id,
                    )

                    _LOGGER.info("MQTT info response type: %s", type(mqtt_info))
                    _LOGGER.info(
                        "MQTT info response (first 800 chars): %s",
                        str(mqtt_info)[:800],
                    )

                    # Merge devices from this home
                    result_data = mqtt_info if isinstance(mqtt_info, dict) else {}

                    devices = (
                        result_data.get("data", [])
                        if isinstance(result_data, dict)
                        else []
                    )
                    total = (
                        result_data.get("total", 0)
                        if isinstance(result_data, dict)
                        else len(devices)
                    )

                    _LOGGER.info(
                        "Devices type: %s, devices count: %s",
                        type(devices),
                        len(devices) if isinstance(devices, list) else "N/A",
                    )
                    _LOGGER.info("Total from API: %s", total)

                    if isinstance(devices, list):
                        for device in devices:
                            device["home_id"] = home_id
                            device["home_name"] = home_name
                            # Set room info from device data
                            room_id = device.get("roomId") or device.get("room_id", "")
                            room_name = device.get("roomName") or device.get(
                                "room_name",
                                "",
                            )
                            device["room_id"] = room_id
                            device["room_name"] = room_name

                        device_dict = {d.get("id"): d for d in devices}
                        all_devices.update(device_dict)
                        total_device_count += total
                        _LOGGER.info(
                            "Added %s devices from home %s",
                            len(devices),
                            home_id,
                        )

                        if total != len(devices):
                            _LOGGER.warning(
                                "WARNING: API reports %s total devices but returned only %s devices",
                                total,
                                len(devices),
                            )
                    else:
                        _LOGGER.warning("Devices data is not a list: %s", type(devices))

                    _LOGGER.info(
                        "Home %s: Found %s devices (total so far: %s)",
                        home_id,
                        total,
                        total_device_count,
                    )

                except Exception:
                    _LOGGER.error("=" * 80)
                    _LOGGER.exception("Get devices for home %s failed", home_id)
                    _LOGGER.error("=" * 80)

            _LOGGER.info("=" * 80)
            _LOGGER.info("Total devices found: %s", total_device_count)
            _LOGGER.info("Unique devices in dict: %s", len(all_devices))
            _LOGGER.info("=" * 80)

            # Initialize auth_info and mqtt_info
            if not self._auth_info:
                self._auth_info = {}
            self._auth_info["home_ids"] = selected_home_ids
            self._auth_info["home_id"] = selected_home_ids[0]
            self._mqtt_info = {"devices": all_devices, "total": total_device_count}
            self._devices = all_devices

            return await self.async_step_confirm()

        # Show home selection form with area name rule option
        _LOGGER.debug("Showing home selection form with area name rule")
        return self.async_show_form(
            step_id="select_home",
            data_schema=self.__get_home_selection_schema(),
            description_placeholders={
                "nick_name": self._user_info.get(
                    "nickName",
                    self._user_info.get("username", "User"),
                ),
            },
            last_step=False,
        )

    def __get_home_selection_schema(self):
        """Get home selection schema for multi-select with area name rule."""
        homes = self._homes or {}

        # Get translation for device count
        device_count_text = (
            self._i18n.translate("config.selector.home_device_count", "devices")
            if self._i18n
            else "{} devices"
        )

        home_options = {
            home_id: f"{home['home_name']} [{home['device_count']} {device_count_text}]"
            for home_id, home in homes.items()
        }

        # Get translated area name rule options
        area_name_rule_options = {}
        if self._i18n:
            area_name_rule_options = {
                AREA_NAME_RULE_NONE: self._i18n.translate(
                    "config.selector.area_name_rule.options.none",
                    "Do not sync",
                ),
                AREA_NAME_RULE_ROOM: self._i18n.translate(
                    "config.selector.area_name_rule.options.room",
                    "Room name",
                ),
                AREA_NAME_RULE_HOME: self._i18n.translate(
                    "config.selector.area_name_rule.options.home",
                    "Home name",
                ),
                AREA_NAME_RULE_HOME_ROOM: self._i18n.translate(
                    "config.selector.area_name_rule.options.home_room",
                    "Home name and Room name",
                ),
            }
        else:
            area_name_rule_options = {
                AREA_NAME_RULE_NONE: "Do not sync",
                AREA_NAME_RULE_ROOM: "Room name",
                AREA_NAME_RULE_HOME: "Home name",
                AREA_NAME_RULE_HOME_ROOM: "Home name and Room name",
            }

        if not home_options:
            _LOGGER.warning("No homes available for selection")
            return vol.Schema(
                {
                    vol.Required("home_ids", default=[]): cv.multi_select({}),
                    vol.Required(
                        "area_name_rule",
                        default=self._area_name_rule,
                    ): vol.In(area_name_rule_options),
                },
            )

        default_home = list(homes.keys())[:1] if homes else []

        return vol.Schema(
            {
                vol.Required("home_ids", default=default_home): cv.multi_select(
                    home_options,
                ),
                vol.Required("area_name_rule", default=self._area_name_rule): vol.In(
                    area_name_rule_options,
                ),
            },
        )

    async def async_step_device_config(self, user_input: dict | None = None):
        """Configure device names and areas."""
        if user_input:
            action = user_input.get("action", "next")

            if action == "skip_all":
                # Skip remaining devices
                return await self.async_step_confirm()

            # Save current device config
            device = self._devices_list[self._current_device_idx]
            device_id = device.get("id") or device.get("deviceId", "")

            self._devices_config[device_id] = {
                "name": user_input.get("device_name", ""),
                "area_id": user_input.get("area_id", ""),
            }

            # Move to next device
            self._current_device_idx += 1

            # Check if there are more devices to configure
            if self._current_device_idx >= len(self._devices_list):
                return await self.async_step_confirm()

        # Show config form for current device
        return await self.__show_device_config_form()

    async def __show_device_config_form(self):
        """Show device configuration form."""
        device = self._devices_list[self._current_device_idx]
        device_id = device.get("id") or device.get("deviceId", "")
        device_name = (
            device.get("deviceName")
            or device.get("name")
            or device.get("productName", "Unknown Device")
        )
        raw_model = (
            device.get("modelName")
            or device.get("model")
            or device.get("productName", "")
        )
        for freq in ["", "(868MHz)", "（868MHz）"]:
            if freq in raw_model:
                self._device_model = raw_model.replace(freq, "").strip()
                break
        device_model = raw_model
        _LOGGER.info("=" * 80)
        _LOGGER.info("device_model: %s", device_model)
        _LOGGER.info("=" * 80)
        # Get home and room info for suggested area
        home_name = device.get("home_name", "")
        room_name = device.get("room_name", "")

        # Calculate suggested area name based on area_name_rule
        suggested_area = self.__get_suggested_area(home_name, room_name)

        # Get existing config if any
        existing_config = self._devices_config.get(device_id, {})
        default_name = existing_config.get("name", device_name)
        default_area = existing_config.get("area_id", suggested_area)

        # Get photo URL for device icon
        photo_url = device.get("photoUrl", "")
        product_info = device.get("productInfo", {})
        if not photo_url and isinstance(product_info, dict):
            photo_url = product_info.get("photoUrl", "")

        # Build area options from rooms in all homes
        area_options = self.__build_area_options()

        total_devices = len(self._devices_list)
        current = self._current_device_idx + 1
        remaining = total_devices - self._current_device_idx

        # Build action options
        action_options = {}

        # Get translations
        next_step_text = (
            self._i18n.translate("config.device_config.action.next", "Next step")
            if self._i18n
            else "Next"
        )
        skip_all_text = (
            self._i18n.translate(
                "config.device_config.action.skip_all",
                "Skip and finish",
            )
            if self._i18n
            else "Skip"
        )
        remaining_devices_text = (
            self._i18n.translate(
                "config.device_config.remaining_devices",
                "devices remaining",
            )
            if self._i18n
            else "devices"
        )

        action_options["next"] = (
            f"{next_step_text} ({remaining} {remaining_devices_text})"
        )

        if remaining > 1:
            action_options["skip_all"] = skip_all_text

        return self.async_show_form(
            step_id="device_config",
            data_schema=vol.Schema(
                {
                    vol.Required("device_name", default=default_name): str,
                    vol.Optional("area_id", default=default_area): vol.In(area_options),
                    vol.Required("action", default="next"): vol.In(action_options),
                },
            ),
            description_placeholders={
                "device_id": device_id,
                "device_model": device_model,
                "home_name": home_name,
                "room_name": room_name,
                "current": current,
                "total": total_devices,
                "photo_url": photo_url,
            },
            last_step=False,
        )

    def __get_suggested_area(self, home_name: str, room_name: str) -> str:
        """Get suggested area name based on area_name_rule."""
        if self._area_name_rule == AREA_NAME_RULE_NONE:
            return ""
        if self._area_name_rule == AREA_NAME_RULE_ROOM:
            return room_name
        if self._area_name_rule == AREA_NAME_RULE_HOME:
            return home_name
        if self._area_name_rule == AREA_NAME_RULE_HOME_ROOM:
            if home_name and room_name:
                return f"{home_name} {room_name}"
            return room_name or home_name
        return room_name

    def __build_area_options(self) -> dict:
        """Build area options from homes and rooms."""
        # Get translation for 'no area'
        no_area_text = (
            self._i18n.translate("config.device_config.no_area", "No area")
            if self._i18n
            else "No area"
        )

        area_options = {"": no_area_text}

        # Add areas based on area_name_rule
        for home_info in self._homes.values():
            home_name = home_info.get("home_name", "")

            if self._area_name_rule in [AREA_NAME_RULE_HOME, AREA_NAME_RULE_HOME_ROOM]:
                if home_name:
                    area_options[home_name] = home_name

            # Add rooms if available
            if self._area_name_rule in [AREA_NAME_RULE_ROOM, AREA_NAME_RULE_HOME_ROOM]:
                for device in self._devices_list:
                    room_name = device.get("room_name", "")
                    if room_name:
                        if (
                            self._area_name_rule == AREA_NAME_RULE_HOME_ROOM
                            and home_name
                        ):
                            area_key = f"{home_name} {room_name}"
                            area_options[area_key] = f"{home_name} {room_name}"
                        else:
                            area_options[room_name] = room_name

        return area_options

    async def async_step_confirm(self, user_input: dict | None = None):
        """Show confirmation and create entry."""
        if user_input is not None:
            # Check if user confirmed
            if user_input.get("confirm", False):
                # User confirmed - create the config entry
                return await self.config_flow_done()
            # User did not confirm - show form again with error
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required("confirm", default=False): bool,
                    },
                ),
                description_placeholders={
                    "user_id": self._user_id,
                    "home_name": self.__get_selected_homes_display(),
                    "device_count": self._mqtt_info.get("total", 0),
                },
                last_step=True,
                errors={"base": "confirm_required"},
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): bool,
                },
            ),
            description_placeholders={
                "user_id": self._user_id,
                "home_name": self.__get_selected_homes_display(),
                "device_count": self._mqtt_info.get("total", 0),
            },
            last_step=True,
        )

    def __get_selected_homes_display(self) -> str:
        """Get display string for selected homes."""
        # 确保 _auth_info 已初始化
        if not self._auth_info:
            return "No homes selected"

        selected_home_ids = self._auth_info.get(
            "home_ids",
            [self._auth_info.get("home_id")],
        )

        if not selected_home_ids or selected_home_ids == [None]:
            return "No homes selected"

        # 确保 _homes 已初始化
        homes = self._homes or {}

        home_names = []
        for home_id in selected_home_ids:
            if home_id:
                home_info = homes.get(home_id, {})
                home_names.append(home_info.get("home_name", str(home_id)))

        if not home_names:
            return "No homes selected"

        if len(home_names) == 1:
            return home_names[0]
        return f"{len(home_names)} homes: {', '.join(home_names)}"

    async def config_flow_done(self):
        """Create or update config entry."""
        await self._cleanup_http_client()

        region_config = REGIONS.get(self._cloud_server) or REGIONS.get(DEFAULT_REGION)

        data = {
            "virtual_did": self._virtual_did,
            "cloud_server": self._cloud_server,
            "integration_language": self._integration_language,
            "storage_path": self._storage_path,
            "user_id": self._user_id,
            "home_id": self._auth_info.get("home_id"),
            "home_ids": self._auth_info.get(
                "home_ids",
                [self._auth_info.get("home_id")],
            ),
            "secure_id": self._secure_id,
            "secure_key": self._secure_key,
            "access_token": self._auth_info.get("access_token"),
            "refresh_token": self._auth_info.get("refresh_token"),
            CONF_TOKEN_EXPIRES_TS: self._auth_info.get("expires_ts"),
            "api_url": region_config.get("api_url"),
            "mqtt_broker": region_config.get("mqtt_broker"),
            "oauth_redirect_url": self._oauth_redirect_url_full,
            "user_info": self._user_info,
            "homes": self._homes,
            "devices": self._devices,
            CONF_AREA_NAME_RULE: self._area_name_rule,
            CONF_DEVICES_CONFIG: self._devices_config,
        }

        # Get user display name for entry title (prefer nickName)
        user_display_name = self._user_info.get("nickName", "").strip()
        if not user_display_name:
            user_display_name = self._user_info.get("email", "").strip()
        if not user_display_name:
            user_display_name = self._user_id

        # Check if we're updating an existing entry
        if hasattr(self, "_update_entry_on_finish") and self._update_entry_on_finish:
            _LOGGER.info(
                "Updating existing config entry: %s",
                self._update_entry_on_finish.entry_id,
            )
            self.hass.config_entries.async_update_entry(
                self._update_entry_on_finish,
                data=data,
            )
            # Reload the entry to apply changes
            await self.hass.config_entries.async_reload(
                self._update_entry_on_finish.entry_id,
            )
            return self.async_create_entry(
                title=f"Heiman Home - {user_display_name}",
                data=data,
            )

        return self.async_create_entry(
            title=f"Heiman Home - {user_display_name}",
            data=data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get options flow handler."""
        return HeimanOptionsFlowHandler(config_entry)


async def _handle_oauth_webhook(hass, webhook_id, request):
    """Handle OAuth2 callback webhook."""
    i18n: HeimanI18n | None = hass.data[DOMAIN].get(webhook_id, {}).get("i18n")
    try:
        data = dict(request.query)
        _LOGGER.debug(
            "OAuth webhook received - webhook_id: %s, query params: %s",
            webhook_id,
            list(data.keys()),
        )

        # Check for error parameters from OAuth provider
        if "error" in data:
            error_desc = data.get("error_description", "Unknown error")
            _LOGGER.error(
                "OAuth error from provider: %s - %s",
                data["error"],
                error_desc,
            )
            _raise_webhook_config_error(
                f"OAuth error: {data['error']} - {error_desc}",
                HeimanErrorCode.CODE_CONFIG_INVALID_INPUT,
            )

        if data.get("code") is None or data.get("state") is None:
            _LOGGER.error(
                "Missing OAuth parameters - code: %s, state: %s",
                "present" if data.get("code") else "missing",
                "present" if data.get("state") else "missing",
            )
            _raise_webhook_config_error(
                "invalid oauth code or state",
                HeimanErrorCode.CODE_CONFIG_INVALID_INPUT,
            )

        # Verify state parameter
        stored_state = hass.data[DOMAIN][webhook_id].get("oauth_state")
        if data["state"] != stored_state:
            _LOGGER.error(
                "OAuth state mismatch - stored: %s, received: %s",
                stored_state,
                data["state"],
            )
            _raise_webhook_config_error(
                f"inconsistent state, {stored_state}!={data['state']}",
                HeimanErrorCode.CODE_CONFIG_INVALID_STATE,
            )

        # Get future and set result
        fut_oauth_code = hass.data[DOMAIN][webhook_id].get("fut_oauth_code")
        if not fut_oauth_code:
            _LOGGER.error(
                "OAuth code future not found - may have been processed already",
            )
            _raise_webhook_config_error("oauth_code_future_not_found")

        # Check if future is already done (duplicate request)
        if fut_oauth_code.done():
            _LOGGER.warning("Duplicate OAuth callback received - ignoring")
            # Return success page anyway to avoid confusing the user
            success_trans = {}
            if i18n:
                success_trans = i18n.translate("oauth2.success") or {}
            return web.Response(
                body=await oauth_redirect_page(
                    title=success_trans.get("title", "Authentication Successful"),
                    content=success_trans.get(
                        "content",
                        "Please close this page and return to Home Assistant",
                    ),
                    button=success_trans.get("button", "Close Page"),
                    success=True,
                ),
                content_type="text/html",
            )

        # Remove future from storage and set result
        hass.data[DOMAIN][webhook_id].pop("fut_oauth_code", None)
        fut_oauth_code.set_result(data["code"])
        _LOGGER.debug("OAuth code received and stored successfully")

        # Prepare success page
        success_trans = {}
        if i18n:
            success_trans = i18n.translate("oauth2.success") or {}

        # Clean up
        hass.data[DOMAIN][webhook_id].pop("oauth_state", None)
        hass.data[DOMAIN][webhook_id].pop("i18n", None)

        return web.Response(
            body=await oauth_redirect_page(
                title=success_trans.get("title", "Authentication Successful"),
                content=success_trans.get(
                    "content",
                    "Please close this page and return to Home Assistant",
                ),
                button=success_trans.get("button", "Close Page"),
                success=True,
            ),
            content_type="text/html",
        )

    except (
        HeimanConfigError,
        KeyError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as err:
        _LOGGER.error("OAuth webhook error: %s", err)
        fail_trans = {}
        if i18n:
            if isinstance(err, HeimanConfigError):
                (
                    i18n.translate(f"oauth2.error_msg.{err.error_code.value}")
                    or err.message
                )
            fail_trans = i18n.translate("oauth2.fail") or {}

        return web.Response(
            body=await oauth_redirect_page(
                title=fail_trans.get("title", "Authentication Failed"),
                content=str(
                    fail_trans.get(
                        "content",
                        ("{error_msg}. Please close this page and try again."),
                    ),
                ).replace("{error_msg}", str(err)),
                button=fail_trans.get("button", "Close Page"),
                success=False,
            ),
            content_type="text/html",
        )


class HeimanOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for Heiman Home."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self._config_entry = config_entry
        self._entry_data = dict(config_entry.data)

    async def async_step_init(self, user_input: dict | None = None):
        """Handle options flow init."""
        if user_input:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "home_id",
                        default=self._entry_data.get("home_id"),
                    ): str,
                },
            ),
        )
