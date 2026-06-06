"""Config flow for Midea LAN."""

from typing import Any

from aiohttp import ClientSession
from midealocal.cloud import (
    PRESET_ACCOUNT_DATA,
    SUPPORTED_CLOUDS,
    MideaCloud,
    get_midea_cloud,
)
from midealocal.const import DeviceType, ProtocolVersion
from midealocal.device import AuthException, MideaDevice
from midealocal.discover import discover
from midealocal.exceptions import SocketException
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
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import _LOGGER, CONF_ACCOUNT, CONF_KEY, CONF_SERVER, CONF_SUBTYPE, DOMAIN
from .device_catalog import MIDEA_DEVICE_NAMES

ADD_WAY = ["discovery", "manually", "list", "cache"]

# Select default cloud without relying on unstable list indexing.
DEFAULT_CLOUD: str = (
    "MSmartHome"
    if "MSmartHome" in SUPPORTED_CLOUDS
    else next(iter(SUPPORTED_CLOUDS), "")
)

SKIP_LOGIN_OPTION = "skip_login_option"


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
        self.unsorted: dict[int, Any] = {}
        self.account: dict = {}
        self.cloud: MideaCloud | None = None
        self.session: ClientSession | None = None
        self._login_mode: str | None = None
        self._login_data: dict[str, str] | None = None
        for device_type, name in MIDEA_DEVICE_NAMES.items():
            self.unsorted[device_type] = name

        sorted_device_names = sorted(self.unsorted.items(), key=lambda x: x[1])
        for item in sorted_device_names:
            self.supports[item[0]] = item[1]
        # preset account
        _acct_hex = format(PRESET_ACCOUNT_DATA[0] ^ PRESET_ACCOUNT_DATA[1], "x")
        self.preset_account: str = bytes.fromhex(
            _acct_hex if len(_acct_hex) % 2 == 0 else "0" + _acct_hex,
        ).decode("utf-8", errors="ignore")
        # preset password
        _pass_hex = format(PRESET_ACCOUNT_DATA[0] ^ PRESET_ACCOUNT_DATA[2], "x")
        self.preset_password: str = bytes.fromhex(
            _pass_hex if len(_pass_hex) % 2 == 0 else "0" + _pass_hex,
        ).decode("utf-8", errors="ignore")
        self.preset_cloud_name: str = DEFAULT_CLOUD

    def _clear_login_state(self) -> None:
        """Clear flow-scoped credentials and mode."""
        self._login_data = None
        self._login_mode = None
        self.cloud = None

    def _already_configured(self, device_id: str, ip_address: str) -> bool:
        """Check device from json with device_id or ip address.

        Returns:
        -------
        True if device is already configured

        """
        for entry in self._async_current_entries():
            if str(device_id) == str(
                entry.data.get(CONF_DEVICE_ID)
            ) or ip_address == entry.data.get(CONF_IP_ADDRESS):
                return True
        return False

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """Define config flow steps.

        Using `async_step_<step_id>` and `async_step_user` will be the first step,
        then select discovery mode

        Returns:
        -------
        Config flow result

        """
        return self.async_show_menu(
            step_id="user",
            menu_options=ADD_WAY,
            description_placeholders={"error": error} if error else None,
        )

    async def async_step_cache(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """Remove cached login data and can input a new one.

        Returns:
        -------
        Config flow result

        """
        # user input data exist
        if user_input is not None:
            self._clear_login_state()
            return await self.async_step_user()
        # show cache info form in UI
        return self.async_show_form(
            step_id="cache",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="remove"): vol.In(
                        ["remove"],
                    ),
                },
            ),
            errors={"base": error} if error else None,
        )

    async def async_step_login(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """User login steps.

        Returns:
        -------
        Config flow result

        """
        # get cloud servers configs
        cloud_servers = await MideaCloud.get_cloud_servers()
        cloud_server_options = list(cloud_servers.values())
        default_server = next(
            (server for server in cloud_server_options if server == DEFAULT_CLOUD),
            cloud_server_options[0],
        )
        cloud_server_options.append(SKIP_LOGIN_OPTION)
        # user input data exist
        if user_input is not None:
            # check skip login option
            if user_input[CONF_SERVER] == SKIP_LOGIN_OPTION:
                # use preset account and DEFAULT_CLOUD cloud
                cloud_server = DEFAULT_CLOUD
                account = self.preset_account
                password = self.preset_password
                login_mode = "preset"
            # use input data
            else:
                _LOGGER.debug("User input login matched")
                cloud_server = user_input[CONF_SERVER]
                account = user_input[CONF_ACCOUNT]
                password = user_input[CONF_PASSWORD]
                login_mode = "input"

            self._login_mode = login_mode

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
                # return to next step after login pass
                return await self.async_step_auto()
            # return error with login failed
            _LOGGER.error(
                "Failed to login with %s account in %s server",
                login_mode,
                cloud_server,
            )
            return await self.async_step_login(error="login_failed")
        # user not login, show login form in UI
        return self.async_show_form(
            step_id="login",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(
                        CONF_SERVER,
                        default=default_server,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=cloud_server_options,
                            translation_key="server",
                        )
                    ),
                },
            ),
            errors={"base": error} if error else None,
        )

    async def async_step_list(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """List all devices and show device info in web UI.

        Returns:
        -------
        Config flow result

        """
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

    async def async_step_discovery(
        self,
        discovery_info: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """Discovery device with auto mode or ip address.

        Returns:
        -------
        Config flow result

        """
        # input is not None, using ip_address to discovery device
        if discovery_info is not None:
            # auto mode, ip_address is None
            if discovery_info[CONF_IP_ADDRESS].lower() == "auto":
                ip_address = None
            # ip exist
            else:
                ip_address = discovery_info[CONF_IP_ADDRESS]
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
            return await self.async_step_discovery(error="no_devices")
        # show discovery device input form with auto or ip address in web UI
        return self.async_show_form(
            step_id="discovery",
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
        """Check cloud login.

        Returns:
        -------
        True if cloud login succeeded

        """
        # set default args with preset account
        if cloud_name is None or account is None or password is None:
            cloud_name = self.preset_cloud_name
            account = self.preset_account
            password = self.preset_password

        if self.session is None:
            self.session = async_create_clientsession(self.hass)

        # init cloud object or force reinit with new one
        if self.cloud is None or force_login:
            self.cloud = get_midea_cloud(
                cloud_name,
                self.session,
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
        _LOGGER.error(
            "Unable to login to %s cloud",
            cloud_name,
        )
        return False

    async def _check_key_from_cloud(
        self,
        appliance_id: int,
        default_key: bool = True,
    ) -> dict[str, Any]:
        """Use preset DEFAULT_CLOUD account to get v3 device token and key.

        Returns:
        -------
        Dictionary of keys

        """
        device = self.devices[appliance_id]

        if self.cloud is None:
            return {"error": "cloud_none"}

        # get device token/key from cloud
        keys = await self.cloud.get_cloud_keys(appliance_id)
        default_keys = await MideaCloud.get_default_keys()
        # use token/key to connect device and confirm token result
        for k, value in keys.items():
            # skip default_key
            if not default_key and k == next(iter(default_keys)):
                continue
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
            if await self.hass.async_add_executor_job(dm.connect):
                try:
                    await self.hass.async_add_executor_job(dm.authenticate)
                except AuthException:
                    _LOGGER.debug("Unable to authenticate")
                    await self.hass.async_add_executor_job(dm.close_socket)
                except SocketException:
                    _LOGGER.debug("Socket closed")
                    await self.hass.async_add_executor_job(dm.close_socket)
                else:
                    await self.hass.async_add_executor_job(dm.close_socket)
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
        """Discovery device detail info.

        Returns:
        -------
        Config flow result

        """
        # input device exist
        if user_input is not None:
            device_id = user_input[CONF_DEVICE]
            if device_id not in self.devices:
                return await self.async_step_auto(error="no_devices")
            device = self.devices[device_id]
            # set device args with protocol decode data
            # then get subtype from cloud, get v3 device token/key from cloud
            self.found_device = {
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: device.get(CONF_TYPE),
                CONF_PROTOCOL: device.get(CONF_PROTOCOL),
                CONF_IP_ADDRESS: device.get(CONF_IP_ADDRESS),
                CONF_PORT: device.get(CONF_PORT),
                CONF_MODEL: device.get(CONF_MODEL),
            }
            # check login cache, show login web if no cache
            if self._login_data is None:
                return await self.async_step_login()
            # login cached exist, cloud is None, reinit and login
            if self.cloud is None and not await self._check_cloud_login(
                cloud_name=self._login_data[CONF_SERVER],
                account=self._login_data[CONF_ACCOUNT],
                password=self._login_data[CONF_PASSWORD],
            ):
                # print error in debug log and show login web
                _LOGGER.debug(
                    "Login with cached %s account failed in %s server",
                    self._login_mode,
                    self._login_data[CONF_SERVER],
                )
                # remove error cache and relogin
                self._clear_login_state()
                return await self.async_step_login()

            # get subtype from cloud
            if self.cloud is not None and (
                device_info := await self.cloud.get_device_info(device_id)
            ):
                # set subtype with model_number
                self.found_device[CONF_NAME] = device_info.get("name")
                self.found_device[CONF_SUBTYPE] = device_info.get("model_number")

            # MUST get a auth passed token/key for v3 device, disable add before pass
            if device.get(CONF_PROTOCOL) == ProtocolVersion.V3:
                # phase 1, try with user input login data
                keys = await self._check_key_from_cloud(device_id)

                # no available key, continue the phase 2
                if not keys.get("token") or not keys.get("key"):
                    _LOGGER.debug(
                        "Can't get valid token with %s account in %s server",
                        self._login_mode,
                        self._login_data[CONF_SERVER],
                    )

                    # exclude: user selected not login and phase 1 is preset account
                    if self._login_mode == "preset":
                        return await self.async_step_auto(
                            error="token_unavailable",
                        )

                    # get key phase 2: reinit cloud with preset account
                    if not await self._check_cloud_login(force_login=True):
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
                        return await self.async_step_auto(
                            error="token_unavailable",
                        )
                # get key pass
                self.found_device[CONF_TOKEN] = keys["token"]
                self.found_device[CONF_KEY] = keys["key"]
                self._clear_login_state()
                return await self.async_step_manually()
            # v1/v2 device add without token/key
            self._clear_login_state()
            return await self.async_step_manually()
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

    async def async_step_manually(
        self,
        user_input: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """Add device with device detail info.

        Returns:
        -------
        Config flow result

        """
        if user_input is not None:
            try:
                bytearray.fromhex(user_input[CONF_TOKEN])
                bytearray.fromhex(user_input[CONF_KEY])
            except ValueError:
                return await self.async_step_manually(error="invalid_token")

            device_id = user_input[CONF_DEVICE_ID]
            # check device, discover already done or only manual add
            if len(self.devices) < 1:
                ip = user_input[CONF_IP_ADDRESS]
                # discover device
                self.devices = await self.hass.async_add_executor_job(
                    lambda: discover(list(self.supports.keys()), ip_address=ip),
                )
                # discover result MUST exist
                if len(self.devices) != 1:
                    return await self.async_step_manually(error="invalid_device_ip")
                # check all the input, disable error add
                device_id = next(iter(self.devices.keys()))

                # check if device_id is correctly set for that IP
                if user_input[CONF_DEVICE_ID] != device_id:
                    return await self.async_step_manually(
                        error="invalid_device_id_for_ip",
                    )

            device = self.devices[device_id]
            if user_input[CONF_IP_ADDRESS] != device.get(CONF_IP_ADDRESS):
                return await self.async_step_manually(
                    error="ip_address_mismatch",
                )
            if user_input[CONF_PROTOCOL] != device.get(CONF_PROTOCOL):
                return await self.async_step_manually(
                    error="protocol_mismatch",
                )

            # try to get token/key with preset account
            if user_input[CONF_PROTOCOL] == ProtocolVersion.V3 and (
                len(user_input[CONF_TOKEN]) == 0 or len(user_input[CONF_KEY]) == 0
            ):
                # init cloud with preset account
                result = await self._check_cloud_login()
                if not result:
                    return await self.async_step_manually(
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
                    return await self.async_step_manually(
                        error="token_unavailable",
                    )

                # set token/key from preset account
                user_input[CONF_KEY] = keys["key"]
                user_input[CONF_TOKEN] = keys["token"]

            self.found_device = {
                CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
                CONF_TYPE: user_input[CONF_TYPE],
                CONF_PROTOCOL: user_input[CONF_PROTOCOL],
                CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                CONF_PORT: user_input[CONF_PORT],
                CONF_MODEL: user_input[CONF_MODEL],
                CONF_TOKEN: user_input[CONF_TOKEN],
                CONF_KEY: user_input[CONF_KEY],
            }

            # check device connection with all the input
            dm = MideaDevice(
                name="",
                device_id=user_input[CONF_DEVICE_ID],
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
            if await self.hass.async_add_executor_job(dm.connect):
                authenticated = False
                try:
                    if user_input[CONF_PROTOCOL] == ProtocolVersion.V3:
                        await self.hass.async_add_executor_job(dm.authenticate)
                    authenticated = True
                except SocketException:
                    _LOGGER.exception("Socket closed")
                except AuthException:
                    _LOGGER.exception(
                        "Unable to authenticate with provided key and token",
                    )
                finally:
                    await self.hass.async_add_executor_job(dm.close_socket)
                if authenticated:
                    device_id = user_input[CONF_DEVICE_ID]
                    device_type = user_input[CONF_TYPE]
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

                    await self.async_set_unique_id(str(device_id))
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=name,
                        data=data,
                    )
            return await self.async_step_manually(
                error="device_auth_failed",
            )
        protocol = self.found_device.get(CONF_PROTOCOL)
        return self.async_show_form(
            step_id="manually",
            data_schema=vol.Schema(
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
            ),
            errors={"base": error} if error else None,
        )
