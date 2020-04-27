"""Config flow to configure the Jenkins integration."""
from jenkinsapi.jenkins import Jenkins
from requests.exceptions import HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_USERNAME

from . import _LOGGER
from .const import DOMAIN


class Server:
    """Class for handling Jenkins server."""

    def __init__(self):
        """Initialize parameters."""
        self.url = None
        self.uid = None
        self.token = None
        self.server = None

    def connect_server(self):
        """Connect to server with Jenkins()."""
        if (self.uid is None) or (self.token is None):
            self.server = Jenkins(self.url)
        else:
            self.server = Jenkins(self.url, self.uid, self.token)

    def get_server(self):
        """Get info in .json from Jenkins server."""
        return self.server

    def get_job_names(self):
        """Get job names from Jenkins server."""
        job_names = [job[0] for job in self.server.get_jobs()]
        return job_names

    def set_url(self, url):
        """Set URL to Jenkins server."""
        self.url = url

    def set_uid(self, uid):
        """Set username to Jenkins server."""
        self.uid = uid

    def set_token(self, token):
        """Set token to Jenkins server."""
        self.token = token


class JenkinsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Jenkins config flow."""

    VERSION = 1
    new_server = Server()

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        if user_input is not None:
            _LOGGER.debug(f"Step 1. Got user_input: {user_input}")
            print(user_input)

            if "url" in user_input:
                self.new_server.set_url(user_input["url"])
                try:
                    await self.hass.async_add_executor_job(
                        self.new_server.connect_server
                    )
                    return await self.async_step_job()
                except HTTPError:
                    return await self.async_step_userLogin()

        _LOGGER.debug(f"Setting up jenkins")

        data_schema = {
            vol.Required(CONF_URL): str,
        }

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema))

    async def async_step_userLogin(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is not None:
            _LOGGER.debug(f"Step 1. Got user_input: {user_input}")
            self.new_server.set_uid(user_input["username"])
            self.new_server.set_token(user_input["token"])
            try:
                await self.hass.async_add_executor_job(self.new_server.connect_server)
                return await self.async_step_job()
            except AttributeError:
                print("AttributError")
                return

        _LOGGER.debug(f"Setting up jenkins")

        data_schema = {vol.Required(CONF_USERNAME): str, vol.Required(CONF_TOKEN): str}

        return self.async_show_form(
            step_id="userLogin", data_schema=vol.Schema(data_schema)
        )

    async def async_step_job(self, user_input=None):
        """Handle selecting which job to add a sensor for."""
        if self.new_server.get_server is None:
            _LOGGER.error("Got to step 2 without an server connection")

        if user_input is not None:
            _LOGGER.debug(f"User decided on the following: {user_input}")

            # TODO: Create and add entity
            return self.async_abort(reason="under_development")

        # TODO: Fix "Detected I/O inside the event loop"
        job_names = await self.hass.async_add_executor_job(
            self.new_server.get_job_names
        )

        data_schema = vol.Schema({vol.Required("JOB_NAME"): vol.In(job_names)})

        return self.async_show_form(step_id="job", data_schema=data_schema)
