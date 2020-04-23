"""Config flow to configure the Jenkins integration."""

from jenkinsapi.jenkins import Jenkins
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

from . import _LOGGER
from .const import CONF_JOB_NAME, DOMAIN


class JenkinsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Jenkins config flow."""

    VERSION = 1

    server = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        if user_input is not None:
            _LOGGER.debug(f"Step 1. Got user_input: {user_input}")

            # TODO: Fix "Detected I/O inside the event loop"
            self.server = Jenkins(user_input["url"])

            return await self.async_step_job()

        _LOGGER.debug(f"Setting up jenkins")

        data_schema = {
            vol.Required(CONF_URL): str,
        }

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema))

    async def async_step_job(self, user_input=None):
        """Handle selecting which job to add a sensor for."""
        if self.server is None:
            _LOGGER.error("Got to step 2 without an server connection")

        if user_input is not None:
            _LOGGER.debug(f"User decided on the following: {user_input}")

            return self.async_create_entry(
                title=user_input[CONF_JOB_NAME],
                data={
                    CONF_URL: self.server.baseurl,
                    CONF_USERNAME: None,
                    CONF_PASSWORD: None,
                    CONF_JOB_NAME: user_input[CONF_JOB_NAME],
                },
            )

        # TODO: Fix "Detected I/O inside the event loop"
        job_names = [job[0] for job in self.server.get_jobs()]

        data_schema = vol.Schema({vol.Required(CONF_JOB_NAME): vol.In(job_names)})

        return self.async_show_form(step_id="job", data_schema=data_schema)
