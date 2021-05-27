"""Config flow to configure Xiaomi Miio."""
import logging
from re import search

from micloud import MiCloud
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_CLOUD_COUNTRY,
    CONF_CLOUD_PASSWORD,
    CONF_CLOUD_SUBDEVICES,
    CONF_CLOUD_USERNAME,
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_GATEWAY,
    CONF_MAC,
    CONF_MANUAL,
    CONF_MODEL,
    DEFAULT_CLOUD_COUNTRY,
    DOMAIN,
    MODELS_ALL,
    MODELS_ALL_DEVICES,
    MODELS_GATEWAY,
    SERVER_COUNTRY_CODES,
)
from .device import ConnectXiaomiDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_GATEWAY_NAME = "Xiaomi Gateway"

DEVICE_SETTINGS = {
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
}
DEVICE_CONFIG = vol.Schema({vol.Required(CONF_HOST): str}).extend(DEVICE_SETTINGS)
DEVICE_MODEL_CONFIG = vol.Schema({vol.Required(CONF_MODEL): vol.In(MODELS_ALL)})
DEVICE_CLOUD_CONFIG = vol.Schema(
    {
        vol.Optional(CONF_CLOUD_USERNAME): str,
        vol.Optional(CONF_CLOUD_PASSWORD): str,
        vol.Optional(CONF_CLOUD_COUNTRY): vol.In(SERVER_COUNTRY_CODES),
        vol.Optional(CONF_MANUAL, default=False)): bool,
    }
)



class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Init object."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        if user_input is not None:
            use_cloud = user_input.get(CONF_CLOUD_SUBDEVICES, False)
            cloud_username = self.config_entry.data.get(CONF_CLOUD_USERNAME)
            cloud_password = self.config_entry.data.get(CONF_CLOUD_PASSWORD)
            cloud_country = self.config_entry.data.get(CONF_CLOUD_COUNTRY)

            if use_cloud and (not cloud_username or not cloud_password or not cloud_country):
                errors["base"] = "cloud_credentials_incomplete"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        settings_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CLOUD_SUBDEVICES,
                    default=self.config_entry.options.get(CONF_CLOUD_SUBDEVICES, False),
                ): bool
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=settings_schema, errors=errors
        )


class XiaomiMiioFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Xiaomi Miio config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self.host = None
        self.mac = None
        self.token = None
        self.model = None
        self.name = None
        self.cloud_username = None
        self.cloud_password = None
        self.cloud_country = None
        self.cloud_devices = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlowHandler:
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_import(self, conf: dict):
        """Import a configuration from config.yaml."""
        self.host = conf[CONF_HOST]
        self.token = conf[CONF_TOKEN]
        self.name = conf.get(CONF_NAME)
        self.model = conf.get(CONF_MODEL)

        self.context.update({"title_placeholders": {"name": f"YAML import {self.host}"}})
        return await self.async_step_connect()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_cloud()

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf discovery."""
        name = discovery_info.get("name")
        self.host = discovery_info.get("host")
        self.mac = discovery_info.get("properties", {}).get("mac")
        if self.mac is None:
            poch = discovery_info.get("properties", {}).get("poch", "")
            result = search(r"mac=\w+", poch)
            if result is not None:
                self.mac = result.group(0).split("=")[1]

        if not name or not self.host or not self.mac:
            return self.async_abort(reason="not_xiaomi_miio")

        self.mac = format_mac(self.mac)

        # Check which device is discovered.
        for gateway_model in MODELS_GATEWAY:
            if name.startswith(gateway_model.replace(".", "-")):
                unique_id = self.mac
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured({CONF_HOST: self.host})

                self.context.update(
                    {"title_placeholders": {"name": f"Gateway {self.host}"}}
                )

                return await self.async_step_cloud()

        for device_model in MODELS_ALL_DEVICES:
            if name.startswith(device_model.replace(".", "-")):
                unique_id = self.mac
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured({CONF_HOST: self.host})

                self.context.update(
                    {"title_placeholders": {"name": f"{device_model} {self.host}"}}
                )

                return await self.async_step_cloud()

        # Discovered device is not yet supported
        _LOGGER.debug(
            "Not yet supported Xiaomi Miio device '%s' discovered with host %s",
            name,
            self.host,
        )
        return self.async_abort(reason="not_xiaomi_miio")
    
    def extract_cloud_info(self, cloud_device_info):
        if self.host is None:
            self.host = cloud_device_info["localip"]
        if self.mac is None:
            self.mac = cloud_device_info["mac"]
        if self.model is None:
            self.model = cloud_device_info["model"]
        if self.name is None:
            self.name = cloud_device_info["name"]
        self.token = cloud_device_info["token"]
    
    async def async_step_cloud(self, user_input=None):
        """Configure a xiaomi miio device through the Miio Cloud."""
        errors = {}
        if user_input is not None:
            if user_input[CONF_MANUAL]:
                return await self.async_step_manual()
            
            cloud_username = user_input.get(CONF_CLOUD_USERNAME)
            cloud_password = user_input.get(CONF_CLOUD_PASSWORD)
            cloud_country = user_input.get(CONF_CLOUD_COUNTRY)
            
            if not cloud_username or not cloud_password or not cloud_country:
                errors["base"] = "cloud_credentials_incomplete"
                return self.async_show_form(step_id="cloud", data_schema=DEVICE_CLOUD_CONFIG, errors=errors)
            
            miio_cloud = MiCloud(cloud_username, cloud_password)
            if not await self.hass.async_add_executor_job(miio_cloud.login):
                errors["base"] = "cloud_login_error"
                return self.async_show_form(step_id="cloud", data_schema=DEVICE_CLOUD_CONFIG, errors=errors)
            
            devices_raw = await self._hass.async_add_executor_job(
                miio_cloud.get_devices, cloud_country
            )
            
            if not devices_raw:
                errors["base"] = "cloud_no_devices"
                return self.async_show_form(step_id="cloud", data_schema=DEVICE_CLOUD_CONFIG, errors=errors)
            
            self.cloud_devices = {}
            for device in devices_raw:
                parent_id = device.get("parent_id")
                if not parent_id:
                    name = device["name"]
                    model = device["model"]
                    list_name = f"{name} - {model}"
                    self.cloud_devices[list_name] = device
            
            self.cloud_username = cloud_username
            self.cloud_password = cloud_password
            self.cloud_country = cloud_country
            
            if self.host is not None:
                for device in self.cloud_devices.values():
                    cloud_host = device.get("localip")
                    if cloud_host == self.host:
                        extract_cloud_info(device)
                        return await self.async_step_connect()
            
            if len(self.cloud_devices) == 1:
                extract_cloud_info(list(self.cloud_devices.values())[0])
                return await self.async_step_connect()

            return await self.async_step_select() 
            
        return self.async_show_form(step_id="cloud", data_schema=DEVICE_CLOUD_CONFIG, errors=errors)

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle multiple cloud devices found."""
        errors = {}
        if user_input is not None:
            cloud_device = self.cloud_devices[user_input["select_device"]]
            extract_cloud_info(cloud_device)
            return await self.async_step_connect()

        select_scheme = vol.Schema(
            {
                vol.Required("select_device"): vol.In(
                    list(self.cloud_devices.keys())
                )
            }
        )

        return self.async_show_form(
            step_id="select", data_schema=select_scheme, errors=errors
        )

    async def async_step_manual(self, user_input=None):
        """Configure a xiaomi miio device Manually."""
        errors = {}
        if user_input is not None:
            self.token = user_input[CONF_TOKEN]
            if user_input.get(CONF_HOST):
                self.host = user_input[CONF_HOST]

            return await self.async_step_connect()

        if self.host:
            schema = vol.Schema(DEVICE_SETTINGS)
        else:
            schema = DEVICE_CONFIG

        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)

    async def async_step_connect(self, user_input=None):
        """Connect to a xiaomi miio device."""
        errors = {}
        if self.host is None or self.token is None:
            return self.async_abort(reason="incomplete_info")
        
        # Try to connect to a Xiaomi Device.
        connect_device_class = ConnectXiaomiDevice(self.hass)
        await connect_device_class.async_connect_device(self.host, self.token)
        device_info = connect_device_class.device_info

        if self.model is None and device_info is not None:
            self.model = device_info.model

        if self.model is None:
            errors["base"] = "cannot_connect"
            return await self.async_step_model(errors=errors)
        
        if self.mac is None and device_info is not None:
            self.mac = format_mac(device_info.mac_address)

        unique_id = self.mac
        await self.async_set_unique_id(
            unique_id, raise_on_progress=False
        )
        self._abort_if_unique_id_configured()

        # Setup Gateways
        for gateway_model in MODELS_GATEWAY:
            if self.model.startswith(gateway_model):
                if self.name is None:
                    self.name = DEFAULT_GATEWAY_NAME
                return self.async_create_entry(
                    title=self.name,
                    data={
                        CONF_FLOW_TYPE: CONF_GATEWAY,
                        CONF_HOST: self.host,
                        CONF_TOKEN: self.token,
                        CONF_MODEL: self.model,
                        CONF_MAC: self.mac,
                        CONF_CLOUD_USERNAME: self.cloud_username,
                        CONF_CLOUD_PASSWORD: self.cloud_password,
                        CONF_CLOUD_COUNTRY: self.cloud_country,
                    },
                )

        # Setup all other Miio Devices
        if self.name is None:
            self.name = self.model

        for device_model in MODELS_ALL_DEVICES:
            if self.model.startswith(device_model):
                return self.async_create_entry(
                    title=self.name,
                    data={
                        CONF_FLOW_TYPE: CONF_DEVICE,
                        CONF_HOST: self.host,
                        CONF_TOKEN: self.token,
                        CONF_MODEL: self.model,
                        CONF_MAC: self.mac,
                        CONF_CLOUD_USERNAME: self.cloud_username,
                        CONF_CLOUD_PASSWORD: self.cloud_password,
                        CONF_CLOUD_COUNTRY: self.cloud_country,
                    },
                )

        errors["base"] = "unknown_device"
        return await self.async_step_model(errors=errors)

    async def async_step_model(self, user_input=None, errors={}):
        """Overwrite model info."""
        if user_input is not None:
            self.model = user_input[CONF_MODEL]
            return await self.async_step_connect()

        return self.async_show_form(step_id="model", data_schema=DEVICE_MODEL_CONFIG, errors=errors)
