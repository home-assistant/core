"""Config flow for Smappee."""
import logging

from pysmappee import helper, mqtt
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS
from homeassistant.helpers import config_entry_oauth2_flow

from . import api
from .const import (
    CONF_HOSTNAME,
    CONF_SERIALNUMBER,
    DOMAIN,
    ENV_CLOUD,
    ENV_LOCAL,
    SUPPORTED_LOCAL_DEVICES,
)


class SmappeeFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config Smappee config flow."""

    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_oauth_create_entry(self, data):
        """Create an entry for the flow."""

        await self.async_set_unique_id(unique_id=f"{DOMAIN}Cloud")
        return self.async_create_entry(title=f"{DOMAIN}Cloud", data=data)

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf discovery."""

        if not discovery_info[CONF_HOSTNAME].startswith(SUPPORTED_LOCAL_DEVICES):
            return self.async_abort(reason="invalid_mdns")

        serial_number = (
            discovery_info[CONF_HOSTNAME].replace(".local.", "").replace("Smappee", "")
        )

        # Check if already configured (local)
        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()

        # Check if already configured (cloud)
        if self.is_cloud_device_already_added():
            return self.async_abort(reason="already_configured_device")

        self.context.update(
            {
                CONF_IP_ADDRESS: discovery_info["host"],
                CONF_SERIALNUMBER: serial_number,
                "title_placeholders": {"name": serial_number},
            }
        )

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None):
        """Confirm zeroconf flow."""
        errors = {}

        # Check if already configured (cloud)
        if self.is_cloud_device_already_added():
            return self.async_abort(reason="already_configured_device")

        if user_input is None:
            serialnumber = self.context.get(CONF_SERIALNUMBER)
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={"serialnumber": serialnumber},
                errors=errors,
            )

        ip_address = self.context.get(CONF_IP_ADDRESS)
        serial_number = self.context.get(CONF_SERIALNUMBER)

        # Attempt to make a connection to the local device
        if helper.is_smappee_genius(serial_number):
            # next generation device, attempt connect to the local mqtt broker
            smappee_mqtt = mqtt.SmappeeLocalMqtt(serial_number=serial_number)
            connect = await self.hass.async_add_executor_job(smappee_mqtt.start_attempt)
            if not connect:
                return self.async_abort(reason="cannot_connect")
        else:
            # legacy devices, without local mqtt broker, try api access
            smappee_api = api.api.SmappeeLocalApi(ip=ip_address)
            logon = await self.hass.async_add_executor_job(smappee_api.logon)
            if logon is None:
                return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=f"{DOMAIN}{serial_number}",
            data={CONF_IP_ADDRESS: ip_address, CONF_SERIALNUMBER: serial_number},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        # If there is a CLOUD entry already, abort a new LOCAL entry
        if self.is_cloud_device_already_added():
            return self.async_abort(reason="already_configured_device")

        return await self.async_step_environment()

    async def async_step_environment(self, user_input=None):
        """Decide environment, cloud or local."""
        if user_input is None:
            return self.async_show_form(
                step_id="environment",
                data_schema=vol.Schema(
                    {
                        vol.Required("environment", default=ENV_CLOUD): vol.In(
                            [ENV_CLOUD, ENV_LOCAL]
                        )
                    }
                ),
                errors={},
            )

        # Environment chosen, request additional host information for LOCAL or OAuth2 flow for CLOUD
        # Ask for host detail
        if user_input["environment"] == ENV_LOCAL:
            return await self.async_step_local()

        # Abort cloud option if a LOCAL entry has already been added
        if user_input["environment"] == ENV_CLOUD and self._async_current_entries():
            return self.async_abort(reason="already_configured_local_device")

        return await self.async_step_pick_implementation()

    async def async_step_local(self, user_input=None):
        """Handle local flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="local",
                data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
                errors={},
            )
        # In a LOCAL setup we still need to resolve the host to serial number
        ip_address = user_input["host"]
        serial_number = None

        # Attempt 1: try to use the local api (older generation) to resolve host to serialnumber
        smappee_api = api.api.SmappeeLocalApi(ip=ip_address)
        logon = await self.hass.async_add_executor_job(smappee_api.logon)
        if logon is not None:
            advanced_config = await self.hass.async_add_executor_job(
                smappee_api.load_advanced_config
            )
            for config_item in advanced_config:
                if config_item["key"] == "mdnsHostName":
                    serial_number = config_item["value"]
        else:
            # Attempt 2: try to use the local mqtt broker (newer generation) to resolve host to serialnumber
            smappee_mqtt = mqtt.SmappeeLocalMqtt()
            connect = await self.hass.async_add_executor_job(smappee_mqtt.start_attempt)
            if not connect:
                return self.async_abort(reason="cannot_connect")

            serial_number = await self.hass.async_add_executor_job(
                smappee_mqtt.start_and_wait_for_config
            )
            await self.hass.async_add_executor_job(smappee_mqtt.stop)
            if serial_number is None:
                return self.async_abort(reason="cannot_connect")

        if serial_number is None or not serial_number.startswith(
            SUPPORTED_LOCAL_DEVICES
        ):
            return self.async_abort(reason="invalid_mdns")

        serial_number = serial_number.replace("Smappee", "")

        # Check if already configured (local)
        await self.async_set_unique_id(serial_number, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{DOMAIN}{serial_number}",
            data={CONF_IP_ADDRESS: ip_address, CONF_SERIALNUMBER: serial_number},
        )

    def is_cloud_device_already_added(self):
        """Check if a CLOUD device has already been added."""
        for entry in self._async_current_entries():
            if entry.unique_id is not None and entry.unique_id == f"{DOMAIN}Cloud":
                return True
        return False
