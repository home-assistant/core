"""Config flow for Midea LAN."""

from operator import itemgetter
from typing import Any, override

from midealocal.cloud import (
    MideaCloud,
    get_default_cloud,
    get_midea_cloud,
    get_preset_account_cloud,
)
from midealocal.const import DeviceType, ProtocolVersion
from midealocal.device import MideaDevice
from midealocal.discover import discover
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOKEN,
    CONF_TYPE,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import _LOGGER, CONF_ACCOUNT, CONF_KEY, CONF_SERVER, CONF_SUBTYPE, DOMAIN
from .device_catalog import MIDEA_DEVICE_NAMES

DEFAULT_CLOUD: str = get_default_cloud()

LOGIN_MODE_PRESET = "preset"
LOGIN_MODE_ACCOUNT = "account"


def _connect_and_close(dm: MideaDevice) -> bool:
    """Connect to the device, always closing the socket afterwards."""
    try:
        return dm.connect(check_protocol=True)
    finally:
        dm.close_socket()


class MideaLanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Define current integration setup steps.

    Use ConfigFlow handle to support config entries
    ConfigFlow will manage the creation of entries from user input, discovery
    """

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """MideaLanConfigFlow class."""
        self.available_device: dict = {}
        self.devices: dict = {}
        self.found_device: dict[str, Any] = {}
        self.supports: dict = {}
        self.cloud: MideaCloud | None = None
        self._login_data: dict[str, str] | None = None
        unsorted = dict(MIDEA_DEVICE_NAMES)

        # sort and assign supports
        self.supports = dict(sorted(unsorted.items(), key=itemgetter(1)))

        # Try the preset account first, as it is usually enough to retrieve most data.
        # Users registered on a different server may not be able to retrieve the
        # required key with their own credentials.
        # If this fails, fall back to user-provided credentials.
        preset_account = get_preset_account_cloud()
        self.preset_account: str = preset_account["username"]
        self.preset_password: str = preset_account["password"]
        self.preset_cloud_name: str = preset_account["cloud_name"]

    def _clear_login_state(self) -> None:
        """Clear flow-scoped credentials and cloud."""
        self._login_data = None
        self.cloud = None

    def _already_configured(self, device_id: str, ip_address: str) -> bool:
        """Check device from json with device_id or ip address."""
        for entry in self._async_current_entries():
            if str(device_id) == str(
                entry.data.get(CONF_DEVICE_ID)
            ) or ip_address == entry.data.get(CONF_IP_ADDRESS):
                return True
        return False

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Start a user flow."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["search", "manually", "list"],
        )

    async def async_step_login_credentials(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """User login steps."""
        # get cloud servers configs
        cloud_servers = await MideaCloud.get_cloud_servers()
        cloud_server_options = list(cloud_servers.values())
        if not cloud_server_options:
            cloud_server_options = [DEFAULT_CLOUD]
        default_server = next(
            (server for server in cloud_server_options if server == DEFAULT_CLOUD),
            cloud_server_options[0],
        )
        # user input data exist
        if user_input is not None:
            cloud_server = user_input[CONF_SERVER]
            account = user_input[CONF_ACCOUNT]
            password = user_input[CONF_PASSWORD]

            # cloud login MUST pass with user input or preset account
            if await self._check_cloud_login(
                cloud_name=cloud_server,
                account=account,
                password=password,
                force_login=True,
            ):
                self._login_data = {
                    CONF_ACCOUNT: account,
                    CONF_PASSWORD: password,
                    CONF_SERVER: cloud_server,
                }
                # resume device processing with the already selected device
                return await self.async_step_auto(
                    user_input={CONF_DEVICE: self.found_device[CONF_DEVICE_ID]},
                )
            # return error with login failed
            _LOGGER.debug(
                "Failed to login to %s cloud with user credentials",
                cloud_server,
            )
            return self._show_login_credentials_form(
                cloud_server_options,
                default_server,
                user_input=user_input,
                error="login_failed",
            )
        # user not login, show login form in UI
        return self._show_login_credentials_form(
            cloud_server_options,
            default_server,
            user_input=None,
            error=error,
        )

    def _show_login_credentials_form(
        self,
        cloud_server_options: list[str],
        default_server: str,
        user_input: dict[str, Any] | None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """Show the login form, retaining any previously entered values."""
        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(
                    CONF_SERVER,
                    default=default_server,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=cloud_server_options,
                    )
                ),
            },
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id="login_credentials",
            data_schema=schema,
            errors={"base": error} if error else None,
        )

    async def async_step_auth_method(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """Select how to authenticate."""

        if user_input is not None:
            if user_input["login_mode"] == LOGIN_MODE_ACCOUNT:
                return await self.async_step_login_credentials()

            # preset selected
            if await self._check_cloud_login(force_login=True):
                self._login_data = {
                    CONF_SERVER: DEFAULT_CLOUD,
                    CONF_ACCOUNT: self.preset_account,
                    CONF_PASSWORD: self.preset_password,
                }
                # resume device processing with the already selected device
                return await self.async_step_auto(
                    user_input={CONF_DEVICE: self.found_device[CONF_DEVICE_ID]},
                )

            return await self.async_step_auth_method(
                error="preset_login_failed",
            )

        return self.async_show_form(
            step_id="auth_method",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "login_mode",
                        default=LOGIN_MODE_PRESET,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                LOGIN_MODE_PRESET,
                                LOGIN_MODE_ACCOUNT,
                            ],
                            translation_key="login_mode",
                        )
                    ),
                }
            ),
            errors={"base": error} if error else None,
        )

    async def async_step_list(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """List all devices and show device info in web UI."""
        if user_input is not None:
            return await self.async_step_user()

        # get all devices list
        all_devices = await self.hass.async_add_executor_job(discover)
        # available devices exist
        if len(all_devices) > 0:
            table = (
                "Appliance code|Type|IP address|SN|Supported\n:--:|:--:|:--:|:--:|:--:"
            )
            for device_id, device in all_devices.items():
                supported = device.get(CONF_TYPE) in self.supports
                table += (
                    f"\n{device_id}|{f'{device.get(CONF_TYPE):02X}'}|"
                    f"{device.get(CONF_IP_ADDRESS)}|"
                    f"{device.get('sn')}|"
                    f"{'YES' if supported else 'NO'}"
                )
        # no available device
        else:
            table = "Not found"
        # show devices list result in UI
        return self.async_show_form(
            step_id="list",
            description_placeholders={"table": table},
            errors={"base": error} if error else None,
        )

    async def async_step_search(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """Search device with auto mode or ip address."""
        # input is not None, using ip_address to discovery device
        if user_input is not None:
            # auto mode, ip_address is None
            if user_input[CONF_IP_ADDRESS].lower() == "auto":
                ip_address = None
            # ip exist
            else:
                ip_address = user_input[CONF_IP_ADDRESS]
            # use midea-local discover() to get devices list with ip_address
            self.devices = await self.hass.async_add_executor_job(
                lambda: discover(list(self.supports.keys()), ip_address=ip_address),
            )
            self.available_device = {}
            for device_id, device in self.devices.items():
                # remove exist devices and only return new devices
                if not self._already_configured(
                    str(device_id),
                    device[CONF_IP_ADDRESS],
                ):
                    # fmt: off
                    self.available_device[device_id] = (
                        f"{device_id} ({self.supports.get(device.get(CONF_TYPE))})"
                    )
                    # fmt: on
            if len(self.available_device) > 0:
                return await self.async_step_auto()
            return await self.async_step_search(error="no_devices")
        # show discovery device input form with auto or ip address in web UI
        return self.async_show_form(
            step_id="search",
            data_schema=vol.Schema(
                {vol.Required(CONF_IP_ADDRESS, default="auto"): str},
            ),
            errors={"base": error} if error else None,
        )

    async def _check_cloud_login(
        self,
        cloud_name: str | None = None,
        account: str | None = None,
        password: str | None = None,
        force_login: bool = False,
    ) -> bool:
        """Check cloud login."""
        # default to preset account
        if cloud_name is None or account is None or password is None:
            cloud_name = self.preset_cloud_name
            account = self.preset_account
            password = self.preset_password

        session = async_get_clientsession(self.hass)

        # init cloud object or force reinit with new one
        if self.cloud is None or force_login:
            self.cloud = get_midea_cloud(
                cloud_name,
                session,
                account,
                password,
            )
        # check cloud login after self.cloud exist
        if await self.cloud.login():
            _LOGGER.debug(
                "Cloud login succeeded for %s",
                cloud_name,
            )
            return True
        _LOGGER.debug(
            "Unable to login to %s cloud",
            cloud_name,
        )
        return False

    async def _check_key_from_cloud(
        self,
        appliance_id: int,
        default_key: bool = True,
    ) -> dict[str, Any]:
        """Use preset DEFAULT_CLOUD account to get v3 device token and key."""
        device = self.devices[appliance_id]

        # _check_cloud_login always succeeds before this is called, setting self.cloud
        assert self.cloud is not None

        # get device token/key from cloud, plus the well-known default keys
        keys = await self.cloud.get_cloud_keys(appliance_id)
        if default_key:
            keys = {**keys, **(await MideaCloud.get_default_keys())}
        # use token/key to connect device and confirm token result
        for k, value in keys.items():
            dm = MideaDevice(
                name="",
                device_id=appliance_id,
                device_type=device.get(CONF_TYPE),
                ip_address=device.get(CONF_IP_ADDRESS),
                port=device.get(CONF_PORT),
                token=value["token"],
                key=value["key"],
                device_protocol=ProtocolVersion.V3,
                model=device.get(CONF_MODEL),
                subtype=device.get(CONF_SUBTYPE, 0),
                attributes={},
            )
            connected = await self.hass.async_add_executor_job(_connect_and_close, dm)
            if connected:
                return value
            # return debug log with failed key
            _LOGGER.debug(
                "Connect device using method %s token/key failed",
                k,
            )
        _LOGGER.debug(
            "Unable to connect device with all the token/key",
        )
        return {"error": "connect_error"}

    async def async_step_auto(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """Discovery device detail info."""
        # input device exist
        if user_input is not None:
            device_id = user_input[CONF_DEVICE]
            device = self.devices[device_id]
            self.found_device = {
                CONF_DEVICE_ID: device_id,
                CONF_NAME: self.supports.get(device.get(CONF_TYPE), str(device_id)),
                CONF_TYPE: device.get(CONF_TYPE),
                CONF_PROTOCOL: device.get(CONF_PROTOCOL),
                CONF_IP_ADDRESS: device.get(CONF_IP_ADDRESS),
                CONF_PORT: device.get(CONF_PORT),
                CONF_MODEL: device.get(CONF_MODEL),
            }

            # MUST get a auth passed token/key for v3 device, disable add before pass
            if device.get(CONF_PROTOCOL) == ProtocolVersion.V3:
                # check login cache, show login web if no cache
                if self._login_data is None or self.cloud is None:
                    return await self.async_step_auth_method()

                # get subtype from cloud
                if device_info := await self.cloud.get_device_info(device_id):
                    # set subtype with model_number
                    if cloud_name := device_info.get("name"):
                        self.found_device[CONF_NAME] = cloud_name
                    self.found_device[CONF_SUBTYPE] = device_info.get("model_number")

                # phase 1, try with user input login data
                keys = await self._check_key_from_cloud(device_id)

                # no available key, continue the phase 2
                if not keys.get("token") or not keys.get("key"):
                    _LOGGER.debug(
                        "Can't get valid token using user credentials on %s",
                        self._login_data[CONF_SERVER],
                    )

                    # get key phase 2: reinit cloud with preset account
                    if not await self._check_cloud_login(force_login=True):
                        self._clear_login_state()
                        return await self.async_step_auto(
                            error="preset_login_failed",
                        )
                    # try to get a passed key, without default_key
                    keys = await self._check_key_from_cloud(
                        device_id,
                        default_key=False,
                    )

                    # phase 2 got no available token/key, disable device add
                    if not keys.get("token") or not keys.get("key"):
                        _LOGGER.debug(
                            "Can't get available token from Midea server for device %s",
                            device_id,
                        )
                        self._clear_login_state()
                        return await self.async_step_auto(
                            error="token_unavailable",
                        )
                # get key pass
                self.found_device[CONF_TOKEN] = keys["token"]
                self.found_device[CONF_KEY] = keys["key"]
                self._clear_login_state()
                return await self._async_create_midea_entry(
                    self._found_device_to_user_input(),
                )
            # v1/v2 device add without token/key, no cloud interaction needed
            self._clear_login_state()
            return await self._async_create_midea_entry(
                self._found_device_to_user_input(),
            )
        # show available device list in UI
        return self.async_show_form(
            step_id="auto",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICE,
                        default=next(iter(self.available_device.keys())),
                    ): vol.In(self.available_device),
                },
            ),
            errors={"base": error} if error else None,
        )

    def _found_device_to_user_input(self) -> dict[str, Any]:
        """Build a manual-step-shaped user_input from the found device."""
        return {
            CONF_DEVICE_ID: self.found_device[CONF_DEVICE_ID],
            CONF_TYPE: self.found_device[CONF_TYPE],
            CONF_IP_ADDRESS: self.found_device[CONF_IP_ADDRESS],
            CONF_PORT: self.found_device[CONF_PORT],
            CONF_PROTOCOL: self.found_device[CONF_PROTOCOL],
            CONF_MODEL: self.found_device[CONF_MODEL],
            CONF_SUBTYPE: self.found_device.get(CONF_SUBTYPE) or 0,
            CONF_TOKEN: self.found_device.get(CONF_TOKEN) or "",
            CONF_KEY: self.found_device.get(CONF_KEY) or "",
        }

    async def _async_create_midea_entry(
        self,
        user_input: dict[str, Any],
    ) -> ConfigFlowResult:
        """Validate device connection with all the input and create the entry."""
        device_id = user_input[CONF_DEVICE_ID]

        # check unique_id before attempting a connection, so a re-add of an
        # already configured but currently offline device aborts (already_configured)
        # instead of failing with device_auth_failed
        await self.async_set_unique_id(str(device_id))
        self._abort_if_unique_id_configured()

        dm = MideaDevice(
            name="",
            device_id=device_id,
            device_type=user_input[CONF_TYPE],
            ip_address=user_input[CONF_IP_ADDRESS],
            port=user_input[CONF_PORT],
            token=user_input[CONF_TOKEN],
            key=user_input[CONF_KEY],
            device_protocol=user_input[CONF_PROTOCOL],
            model=user_input[CONF_MODEL],
            subtype=user_input[CONF_SUBTYPE],
            attributes={},
        )
        connected = await self.hass.async_add_executor_job(_connect_and_close, dm)
        if connected:
            device_type = user_input[CONF_TYPE]
            found_name = self.found_device.get(CONF_NAME)
            if isinstance(found_name, str) and found_name:
                name = found_name
            else:
                name = self.supports.get(device_type, str(device_id))
            data = {
                CONF_NAME: name,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: device_type,
                CONF_PROTOCOL: user_input[CONF_PROTOCOL],
                CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                CONF_PORT: user_input[CONF_PORT],
                CONF_MODEL: user_input[CONF_MODEL],
                CONF_SUBTYPE: user_input[CONF_SUBTYPE],
                CONF_TOKEN: user_input[CONF_TOKEN],
                CONF_KEY: user_input[CONF_KEY],
            }

            return self.async_create_entry(
                title=name,
                data=data,
            )
        return self._show_manually_form(user_input, error="device_auth_failed")

    async def async_step_manually(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """Add device with device detail info."""
        if user_input is not None:
            try:
                bytearray.fromhex(user_input[CONF_TOKEN])
                bytearray.fromhex(user_input[CONF_KEY])
            except ValueError:
                return self._show_manually_form(user_input, error="invalid_token")

            device_id = user_input[CONF_DEVICE_ID]
            # (re)discover whenever the requested device isn't already known,
            # so correcting the IP/device_id and resubmitting can succeed
            if device_id not in self.devices:
                ip = user_input[CONF_IP_ADDRESS]
                # discover device
                self.devices = await self.hass.async_add_executor_job(
                    lambda: discover(list(self.supports.keys()), ip_address=ip),
                )
                # discover result MUST exist
                if len(self.devices) != 1:
                    return self._show_manually_form(
                        user_input, error="invalid_device_ip"
                    )
                # check all the input, disable error add
                device_id = next(iter(self.devices.keys()))

                # check if device_id is correctly set for that IP
                if user_input[CONF_DEVICE_ID] != device_id:
                    return self._show_manually_form(
                        user_input,
                        error="invalid_device_id_for_ip",
                    )

            device = self.devices[device_id]
            if user_input[CONF_IP_ADDRESS] != device.get(CONF_IP_ADDRESS):
                return self._show_manually_form(
                    user_input,
                    error="ip_address_mismatch",
                )
            if user_input[CONF_PROTOCOL] != device.get(CONF_PROTOCOL):
                return self._show_manually_form(
                    user_input,
                    error="protocol_mismatch",
                )
            if user_input[CONF_TYPE] != device.get(CONF_TYPE):
                return self._show_manually_form(
                    user_input,
                    error="type_mismatch",
                )

            # try to get token/key with preset account
            if user_input[CONF_PROTOCOL] == ProtocolVersion.V3 and (
                len(user_input[CONF_TOKEN]) == 0 or len(user_input[CONF_KEY]) == 0
            ):
                # init cloud with preset account
                result = await self._check_cloud_login()
                if not result:
                    return self._show_manually_form(
                        user_input,
                        error="preset_login_failed",
                    )
                # try to get a passed key
                keys = await self._check_key_from_cloud(int(user_input[CONF_DEVICE_ID]))

                # no available token/key, disable device add
                if not keys.get("token") or not keys.get("key"):
                    _LOGGER.debug(
                        "Can't get a valid token from Midea server for device %s",
                        user_input[CONF_DEVICE_ID],
                    )
                    return self._show_manually_form(
                        user_input,
                        error="token_unavailable",
                    )

                # set token/key from preset account
                user_input[CONF_KEY] = keys["key"]
                user_input[CONF_TOKEN] = keys["token"]

            self.found_device = {
                CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
                CONF_NAME: self.found_device.get(CONF_NAME),
                CONF_TYPE: user_input[CONF_TYPE],
                CONF_PROTOCOL: user_input[CONF_PROTOCOL],
                CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                CONF_PORT: user_input[CONF_PORT],
                CONF_MODEL: user_input[CONF_MODEL],
                CONF_TOKEN: user_input[CONF_TOKEN],
                CONF_KEY: user_input[CONF_KEY],
            }

            return await self._async_create_midea_entry(user_input)
        return self._show_manually_form(user_input, error)

    def _show_manually_form(
        self,
        user_input: dict[str, Any] | None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """Show the manual step form, retaining any previously entered values."""
        protocol = self.found_device.get(CONF_PROTOCOL)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEVICE_ID,
                    default=self.found_device.get(CONF_DEVICE_ID),
                ): int,
                vol.Required(
                    CONF_TYPE,
                    default=(self.found_device.get(CONF_TYPE) or DeviceType.AC),
                ): vol.In(self.supports),
                vol.Required(
                    CONF_IP_ADDRESS,
                    default=self.found_device.get(CONF_IP_ADDRESS),
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=(self.found_device.get(CONF_PORT) or 6444),
                ): int,
                vol.Required(
                    CONF_PROTOCOL,
                    default=(protocol or ProtocolVersion.V3),
                ): vol.In(
                    [protocol] if protocol else ProtocolVersion,
                ),
                vol.Required(
                    CONF_MODEL,
                    default=(self.found_device.get(CONF_MODEL) or "Unknown"),
                ): str,
                vol.Required(
                    CONF_SUBTYPE,
                    default=(self.found_device.get(CONF_SUBTYPE) or 0),
                ): int,
                vol.Optional(
                    CONF_TOKEN,
                    default=(self.found_device.get(CONF_TOKEN) or ""),
                ): str,
                vol.Optional(
                    CONF_KEY,
                    default=(self.found_device.get(CONF_KEY) or ""),
                ): str,
            },
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id="manually",
            data_schema=schema,
            errors={"base": error} if error else None,
        )
