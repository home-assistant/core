"""Config flow for Midea LAN."""

from pathlib import Path
from typing import Any, cast

from aiohttp import ClientSession
from midealocal.cloud import (
    PRESET_ACCOUNT_DATA,
    SUPPORTED_CLOUDS,
    MideaCloud,
    get_midea_cloud,
)
from midealocal.const import ProtocolVersion
from midealocal.device import AuthException, MideaDevice
from midealocal.discover import discover
from midealocal.exceptions import SocketException
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_CUSTOMIZE,
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_TOKEN,
    CONF_TYPE,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.json import save_json
from homeassistant.util.json import load_json

from .const import (
    _LOGGER,
    CONF_ACCOUNT,
    CONF_KEY,
    CONF_MODEL,
    CONF_REFRESH_INTERVAL,
    CONF_SERVER,
    CONF_SUBTYPE,
    DOMAIN,
    EXTRA_CONTROL,
    EXTRA_SENSOR,
)
from .devices import MIDEA_DEVICES

ADD_WAY = {
    "discovery": "Discover automatically",
    "manually": "Configure manually",
    "list": "List all appliances only",
    "cache": "Remove login cache",
}

# Select DEFAULT_CLOUD from the list of supported cloud
DEFAULT_CLOUD: str = list(SUPPORTED_CLOUDS)[3]

STORAGE_PATH = f".storage/{DOMAIN}"

SKIP_LOGIN = "Skip Login (input any user/password)"


class MideaLanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Define current integration setup steps.

    Use ConfigFlow handle to support config entries
    ConfigFlow will manage the creation of entries from user input, discovery
    """

    VERSION = 2
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
        for device_type, device_info in MIDEA_DEVICES.items():
            self.unsorted[device_type] = device_info["name"]

        sorted_device_names = sorted(self.unsorted.items(), key=lambda x: x[1])
        for item in sorted_device_names:
            self.supports[item[0]] = item[1]
        # preset account
        self.preset_account: str = bytes.fromhex(
            format((PRESET_ACCOUNT_DATA[0] ^ PRESET_ACCOUNT_DATA[1]), "X"),
        ).decode("utf-8", errors="ignore")
        # preset password
        self.preset_password: str = bytes.fromhex(
            format((PRESET_ACCOUNT_DATA[0] ^ PRESET_ACCOUNT_DATA[2]), "X"),
        ).decode("utf-8", errors="ignore")
        self.preset_cloud_name: str = DEFAULT_CLOUD

    def _save_device_config(self, data: dict[str, Any]) -> None:
        """Save device config to json file with device id."""
        storage_path = Path(self.hass.config.path(STORAGE_PATH))
        storage_path.mkdir(parents=True, exist_ok=True)
        record_file = storage_path.joinpath(f"{data[CONF_DEVICE_ID]!s}.json")
        save_json(str(record_file), data)

    def _load_device_config(self, device_id: str) -> Any:
        """Load device config from json file with device id.

        Returns:
        -------
        Device configuration (json)

        """
        record_file = Path(
            self.hass.config.path(f"{STORAGE_PATH}", f"{device_id}.json"),
        )
        if record_file.exists():
            with record_file.open(encoding="utf-8") as f:
                return load_json(f.name, default={})
        return {}

    @staticmethod
    def _check_storage_device(device: dict, storage_device: dict) -> bool:
        """Check input device with storage_device.

        Returns:
        -------
        True if storage device exist

        """
        if storage_device.get(CONF_SUBTYPE) is None:
            return False
        return not (
            device.get(CONF_PROTOCOL) == ProtocolVersion.V3
            and (
                storage_device.get(CONF_TOKEN) is None
                or storage_device.get(CONF_KEY) is None
            )
        )

    def _already_configured(self, device_id: str, ip_address: str) -> bool:
        """Check device from json with device_id or ip address.

        Returns:
        -------
        True if device is already configured

        """
        for entry in self._async_current_entries():
            if device_id == entry.data.get(
                CONF_DEVICE_ID,
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
        # user select a device discovery mode
        if user_input is not None:
            # default is auto discovery mode
            if user_input["action"] == "discovery":
                return await self.async_step_discovery()
            # manual input device detail
            if user_input["action"] == "manually":
                self.found_device = {}
                return await self.async_step_manually()
            # remove cached login data and input new one
            if user_input["action"] == "cache":
                return await self.async_step_cache()
            # only list all devices
            return await self.async_step_list()
        # user not input, show device discovery select form in UI
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("action", default="discovery"): vol.In(ADD_WAY)},
            ),
            errors={"base": error} if error else None,
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
            # key is not None
            if self.hass.data.get(DOMAIN):
                self.hass.data[DOMAIN].pop("login_data", None)
                self.hass.data[DOMAIN].pop("login_mode", None)
            return await self.async_step_user()
        # show cache info form in UI
        return self.async_show_form(
            step_id="cache",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="remove"): vol.In(
                        {"action": "remove"},
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
        default_keys = await MideaCloud.get_default_keys()
        # add skip login option to web UI with key 99
        cloud_servers[next(iter(default_keys))] = SKIP_LOGIN
        # user input data exist
        if user_input is not None:
            if not self.hass.data.get(DOMAIN):
                self.hass.data[DOMAIN] = {}
            # check skip login option
            if user_input[CONF_SERVER] == next(iter(default_keys)):
                # use preset account and DEFAULT_CLOUD cloud
                _LOGGER.debug("Skip login matched, cloud_servers: %s", cloud_servers)
                # get DEFAULT_CLOUD key from dict
                key = next(
                    key
                    for key, value in cloud_servers.items()
                    if value == DEFAULT_CLOUD
                )
                cloud_server = cloud_servers[key]
                account = self.preset_account
                password = self.preset_password
                # set a login_mode flag
                self.hass.data[DOMAIN]["login_mode"] = "preset"
            # use input data
            else:
                _LOGGER.debug("User input login matched")
                cloud_server = cloud_servers[user_input[CONF_SERVER]]
                account = user_input[CONF_ACCOUNT]
                password = user_input[CONF_PASSWORD]
                # set a login_mode flag
                self.hass.data[DOMAIN]["login_mode"] = "input"

            # cloud login MUST pass with user input or perset account
            if await self._check_cloud_login(
                cloud_name=cloud_server,
                account=account,
                password=password,
                force_login=True,
            ):
                # save passed account to cache, available before HA reboot
                self.hass.data[DOMAIN]["login_data"] = {
                    CONF_ACCOUNT: account,
                    CONF_PASSWORD: password,
                    CONF_SERVER: cloud_server,
                }
                # return to next step after login pass
                return await self.async_step_auto()
            # return error with login failed
            _LOGGER.error(
                "Failed to login with %s account in %s server",
                self.hass.data[DOMAIN]["login_mode"],
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
                    vol.Required(CONF_SERVER, default=1): vol.In(cloud_servers),
                },
            ),
            errors={"base": error} if error else None,
        )

    async def async_step_list(
        self,
        error: str | None = None,
    ) -> ConfigFlowResult:
        """List all devices and show device info in web UI.

        Returns:
        -------
        Config flow result

        """
        # get all devices list
        all_devices = discover()
        # available devices exist
        if len(all_devices) > 0:
            table = (
                "Appliance code|Type|IP address|SN|Supported\n:--:|:--:|:--:|:--:|:--:"
            )
            green = "<font color=gree>YES</font>"
            red = "<font color=red>NO</font>"
            for device_id, device in all_devices.items():
                supported = device.get(CONF_TYPE) in self.supports
                table += (
                    f"\n{device_id}|{f'{device.get(CONF_TYPE):02X}'}|"
                    f"{device.get(CONF_IP_ADDRESS)}|"
                    f"{device.get('sn')}|"
                    f"{green if supported else red}"
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
            self.devices = discover(list(self.supports.keys()), ip_address=ip_address)
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
        # set default args with perset account
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
                "Using account %s login to %s cloud pass",
                account,
                cloud_name,
            )
            return True
        _LOGGER.error(
            "Unable to use account %s login to %s cloud",
            account,
            cloud_name,
        )
        return False

    async def _check_key_from_cloud(
        self,
        appliance_id: int,
        default_key: bool = True,
    ) -> dict[str, Any]:
        """Use perset DEFAULT_CLOUD account to get v3 device token and key.

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
                subtype=0,
                attributes={},
            )
            if dm.connect():
                try:
                    dm.authenticate()
                except AuthException:
                    _LOGGER.debug("Unable to authenticate")
                    dm.close_socket()
                except SocketException:
                    _LOGGER.debug("Socket closed")
                else:
                    dm.close_socket()
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
            storage_device = self._load_device_config(device_id)
            # device config already exist, load from local json without cloud
            if self._check_storage_device(device, storage_device):
                self.found_device = {
                    CONF_DEVICE_ID: device_id,
                    CONF_TYPE: device.get(CONF_TYPE),
                    CONF_PROTOCOL: device.get(CONF_PROTOCOL),
                    CONF_IP_ADDRESS: device.get(CONF_IP_ADDRESS),
                    CONF_PORT: device.get(CONF_PORT),
                    CONF_MODEL: device.get(CONF_MODEL),
                    CONF_NAME: storage_device.get(CONF_NAME),
                    CONF_SUBTYPE: storage_device.get(CONF_SUBTYPE),
                    CONF_TOKEN: storage_device.get(CONF_TOKEN),
                    CONF_KEY: storage_device.get(CONF_KEY),
                }
                _LOGGER.debug(
                    "Loaded configuration for device %s from storage",
                    device_id,
                )
                return await self.async_step_manually()
            # device config not exist in local
            # check login cache, show login web if no cache
            if not self.hass.data.get(DOMAIN) or not self.hass.data[DOMAIN].get(
                "login_data",
            ):
                return await self.async_step_login()
            # login cached exist, cloud is None, reinit and login
            if self.cloud is None and not await self._check_cloud_login(
                cloud_name=self.hass.data[DOMAIN]["login_data"][CONF_SERVER],
                account=self.hass.data[DOMAIN]["login_data"][CONF_ACCOUNT],
                password=self.hass.data[DOMAIN]["login_data"][CONF_PASSWORD],
            ):
                # print error in debug log and show login web
                _LOGGER.debug(
                    "Login with cached %s account %s failed in %s server",
                    self.hass.data[DOMAIN].get("login_mode"),
                    self.hass.data[DOMAIN]["login_data"][CONF_ACCOUNT],
                    self.hass.data[DOMAIN]["login_data"][CONF_SERVER],
                )
                # remove error cache and relogin
                self.hass.data[DOMAIN].pop("login_data", None)
                self.hass.data[DOMAIN].pop("login_mode", None)
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
                        self.hass.data[DOMAIN]["login_mode"],
                        self.hass.data[DOMAIN]["login_data"][CONF_SERVER],
                    )

                    # exclude: user selected not login and phase 1 is preset account
                    if self.hass.data[DOMAIN]["login_mode"] == "preset":
                        return await self.async_step_auto(
                            error="can't get valid token from Midea server",
                        )

                    # get key phase 2: reinit cloud with preset account
                    if not await self._check_cloud_login(force_login=True):
                        return await self.async_step_auto(
                            error="Perset account login failed!",
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
                            error=(
                                f"Can't get available token from Midea server"
                                f" for device {device_id}"
                            ),
                        )
                # get key pass
                self.found_device[CONF_TOKEN] = keys["token"]
                self.found_device[CONF_KEY] = keys["key"]
                return await self.async_step_manually()
            # v1/v2 device add without token/key
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
                self.devices = discover(
                    list(self.supports.keys()),
                    ip_address=ip,
                )
                # discover result MUST exist
                if len(self.devices) != 1:
                    return await self.async_step_manually(error="invalid_device_ip")
                # check all the input, disable error add
                device_id = next(iter(self.devices.keys()))

                # check if device_id is correctly set for that IP
                if user_input[CONF_DEVICE_ID] != device_id:
                    return await self.async_step_manually(
                        error=f"For ip {ip} the device_id MUST be {device_id}",
                    )

            device = self.devices[device_id]
            if user_input[CONF_IP_ADDRESS] != device.get(CONF_IP_ADDRESS):
                return await self.async_step_manually(
                    error=f"ip_address MUST be {device.get(CONF_IP_ADDRESS)}",
                )
            if user_input[CONF_PROTOCOL] != device.get(CONF_PROTOCOL):
                return await self.async_step_manually(
                    error=f"protocol MUST be {device.get(CONF_PROTOCOL)}",
                )

            # try to get token/key with preset account
            if user_input[CONF_PROTOCOL] == ProtocolVersion.V3 and (
                len(user_input[CONF_TOKEN]) == 0 or len(user_input[CONF_KEY]) == 0
            ):
                # init cloud with preset account
                result = await self._check_cloud_login()
                if not result:
                    return await self.async_step_manually(
                        error="Perset account login failed!",
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
                        error=(
                            f"Can't get a valid token from Midea server"
                            f" for device {user_input[CONF_DEVICE_ID]}"
                        ),
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
                subtype=0,
                attributes={},
            )
            if dm.connect():
                try:
                    if user_input[CONF_PROTOCOL] == ProtocolVersion.V3:
                        dm.authenticate()
                except SocketException:
                    _LOGGER.exception("Socket closed")
                except AuthException:
                    _LOGGER.exception(
                        "Unable to authenticate with provided key and token",
                    )
                    dm.close_socket()
                else:
                    dm.close_socket()
                    device_id = user_input[CONF_DEVICE_ID]
                    data = {
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: user_input[CONF_TYPE],
                        CONF_PROTOCOL: user_input[CONF_PROTOCOL],
                        CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_MODEL: user_input[CONF_MODEL],
                        CONF_SUBTYPE: user_input[CONF_SUBTYPE],
                        CONF_TOKEN: user_input[CONF_TOKEN],
                        CONF_KEY: user_input[CONF_KEY],
                    }
                    # save device json config when adding new device
                    self._save_device_config(data)
                    # unique identifier
                    await self.async_set_unique_id(device_id)
                    self._abort_if_unique_id_configured()
                    # finish add device entry
                    return self.async_create_entry(
                        title=f"{user_input[CONF_NAME]}",
                        data=data,
                    )
            return await self.async_step_manually(
                error="Device auth failed with input config",
            )
        protocol = self.found_device.get(CONF_PROTOCOL)
        return self.async_show_form(
            step_id="manually",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=(
                            self.found_device.get(CONF_NAME)
                            if self.found_device.get(CONF_NAME)
                            else self.supports.get(self.found_device.get(CONF_TYPE))
                        ),
                    ): str,
                    vol.Required(
                        CONF_DEVICE_ID,
                        default=self.found_device.get(CONF_DEVICE_ID),
                    ): int,
                    vol.Required(
                        CONF_TYPE,
                        default=(
                            self.found_device.get(CONF_TYPE)
                            if self.found_device.get(CONF_TYPE)
                            else 0xAC
                        ),
                    ): vol.In(self.supports),
                    vol.Required(
                        CONF_IP_ADDRESS,
                        default=self.found_device.get(CONF_IP_ADDRESS),
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=(
                            self.found_device.get(CONF_PORT)
                            if self.found_device.get(CONF_PORT)
                            else 6444
                        ),
                    ): int,
                    vol.Required(
                        CONF_PROTOCOL,
                        default=protocol or ProtocolVersion.V3,
                    ): vol.In(
                        [protocol] if protocol else ProtocolVersion,
                    ),
                    vol.Required(
                        CONF_MODEL,
                        default=(
                            self.found_device.get(CONF_MODEL)
                            if self.found_device.get(CONF_MODEL)
                            else "Unknown"
                        ),
                    ): str,
                    vol.Required(
                        CONF_SUBTYPE,
                        default=(
                            self.found_device.get(CONF_SUBTYPE)
                            if self.found_device.get(CONF_SUBTYPE)
                            else 0
                        ),
                    ): int,
                    vol.Optional(
                        CONF_TOKEN,
                        default=(
                            self.found_device.get(CONF_TOKEN)
                            if self.found_device.get(CONF_TOKEN)
                            else ""
                        ),
                    ): str,
                    vol.Optional(
                        CONF_KEY,
                        default=(
                            self.found_device.get(CONF_KEY)
                            if self.found_device.get(CONF_KEY)
                            else ""
                        ),
                    ): str,
                },
            ),
            errors={"base": error} if error else None,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow with MideaLanOptionsFlowHandler.

        Returns:
        -------
        Config flow options handler

        """
        return MideaLanOptionsFlowHandler(config_entry)


class MideaLanOptionsFlowHandler(OptionsFlow):
    """define an Options Flow Handler to update the options of a config entry."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._device_type = config_entry.data.get(CONF_TYPE)
        if self._device_type is None:
            self._device_type = 0xAC
        if CONF_SENSORS in self._config_entry.options:
            for key in self._config_entry.options[CONF_SENSORS]:
                if key not in MIDEA_DEVICES[self._device_type]["entities"]:
                    self._config_entry.options[CONF_SENSORS].remove(key)
        if CONF_SWITCHES in self._config_entry.options:
            for key in self._config_entry.options[CONF_SWITCHES]:
                if key not in MIDEA_DEVICES[self._device_type]["entities"]:
                    self._config_entry.options[CONF_SWITCHES].remove(key)

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the options.

        Returns:
        -------
        Config flow result

        """
        if self._device_type == CONF_ACCOUNT:
            return self.async_abort(reason="account_option")
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        sensors = {}
        switches = {}
        for attribute, attribute_config in cast(
            "dict",
            MIDEA_DEVICES[cast("int", self._device_type)]["entities"],
        ).items():
            attribute_name = (
                attribute if isinstance(attribute, str) else attribute.value
            )
            if attribute_config.get("type") in EXTRA_SENSOR:
                sensors[attribute_name] = attribute_config.get("name")
            elif attribute_config.get(
                "type",
            ) in EXTRA_CONTROL and not attribute_config.get("default"):
                switches[attribute_name] = attribute_config.get("name")
        ip_address = self._config_entry.options.get(CONF_IP_ADDRESS, None)
        if ip_address is None:
            ip_address = self._config_entry.data.get(CONF_IP_ADDRESS, None)
        refresh_interval = self._config_entry.options.get(CONF_REFRESH_INTERVAL, 30)
        extra_sensors = list(
            set(sensors.keys()) & set(self._config_entry.options.get(CONF_SENSORS, [])),
        )
        extra_switches = list(
            set(switches.keys())
            & set(self._config_entry.options.get(CONF_SWITCHES, [])),
        )
        customize = self._config_entry.options.get(CONF_CUSTOMIZE, "")
        data_schema = vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS, default=ip_address): str,
                vol.Required(CONF_REFRESH_INTERVAL, default=refresh_interval): int,
            },
        )
        if len(sensors) > 0:
            data_schema = data_schema.extend(
                {
                    vol.Required(
                        CONF_SENSORS,
                        default=extra_sensors,
                    ): cv.multi_select(sensors),
                },
            )
        if len(switches) > 0:
            data_schema = data_schema.extend(
                {
                    vol.Required(
                        CONF_SWITCHES,
                        default=extra_switches,
                    ): cv.multi_select(switches),
                },
            )
        data_schema = data_schema.extend(
            {
                vol.Optional(
                    CONF_CUSTOMIZE,
                    default=customize,
                ): str,
            },
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)
