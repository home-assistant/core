"""Config flow to configure the Jenkins integration."""
from jenkinsapi.jenkins import Jenkins
from requests.exceptions import HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL, CONF_USERNAME

from . import _LOGGER
from .const import CONF_JOB_NAME, DOMAIN


class JenkinsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Jenkins config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        if user_input is not None:
            _LOGGER.debug(f"Step 1. Got user_input: {user_input}")

            self.url = user_input[CONF_URL]
            self.username = (
                user_input[CONF_USERNAME] if CONF_USERNAME in user_input else None
            )
            self.token = user_input[CONF_TOKEN] if CONF_TOKEN in user_input else None

            try:
                self.server = await self.hass.async_add_executor_job(
                    Jenkins, self.url, self.username, self.token
                )
                return await self.async_step_job()
            except HTTPError as err:
                _LOGGER.error(err)
                # return await self.async_step_userLogin()

        _LOGGER.debug(f"Setting up jenkins")

        data_schema = {
            vol.Required(CONF_URL): str,
            vol.Optional(CONF_USERNAME): str,
            vol.Optional(CONF_TOKEN): str,
        }

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema))

    async def async_step_job(self, user_input=None):
        """Handle selecting which job to add a sensor for."""
        if self.server is None:
            _LOGGER.error("Got to step 2 without an server connection")

        if user_input is not None:
            _LOGGER.debug(f"User decided on the following: {user_input}")

            self.job_name = user_input[CONF_JOB_NAME]

            return self.async_create_entry(
                title=user_input[CONF_JOB_NAME],
                data={
                    CONF_URL: self.server.baseurl,
                    CONF_USERNAME: self.username,
                    CONF_PASSWORD: self.token,
                    CONF_JOB_NAME: self.job_name,
                },
            )

        job_names = await self.hass.async_add_executor_job(self.get_job_names)

        data_schema = vol.Schema({vol.Required(CONF_JOB_NAME): vol.In(job_names)})

        return self.async_show_form(step_id="job", data_schema=data_schema)

    def get_job_names(self):
        """Return the list of job names."""
        return [job[0] for job in self.server.get_jobs()]
