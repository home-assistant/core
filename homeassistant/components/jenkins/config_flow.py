"""Config flow to configure the Jenkins integration."""
from jenkinsapi.jenkins import Jenkins
from requests.exceptions import HTTPError, MissingSchema
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_USERNAME

from . import _LOGGER
from .const import CONF_JOB_NAME, DOMAIN


class JenkinsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Jenkins config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_TOKEN): str,
            }
        )

        if user_input is not None:
            self.url = user_input[CONF_HOST]
            self.username = (
                user_input[CONF_USERNAME] if CONF_USERNAME in user_input else None
            )
            self.token = user_input[CONF_TOKEN] if CONF_TOKEN in user_input else None

            try:
                self.server = await self.hass.async_add_executor_job(
                    Jenkins, self.url, self.username, self.token
                )
                _LOGGER.debug(f"Successfully connected to host: {self.url}")
                return await self.async_step_job()
            except MissingSchema:
                return self.async_show_form(
                    step_id="user",
                    data_schema=data_schema,
                    errors={"base": "missing_schema"},
                )
            except HTTPError as error:
                if error.response.status_code == 403 and self.username is None:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=data_schema,
                        errors={"base": "credentials_needed"},
                    )
                elif error.response.status_code == 403:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=data_schema,
                        errors={"base": "invalid_credentials"},
                    )
                elif error.response.status_code == 404:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=data_schema,
                        errors={"base": "invalid_host"},
                    )

        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_job(self, user_input=None):
        """Handle selecting which job to add a sensor for."""
        if user_input is not None:
            self.job_name = user_input[CONF_JOB_NAME]
            _LOGGER.debug(f"Creating entry for {self.job_name}.")

            return self.async_create_entry(
                title=user_input[CONF_JOB_NAME],
                data={
                    CONF_HOST: self.server.baseurl,
                    CONF_USERNAME: self.username,
                    CONF_TOKEN: self.token,
                    CONF_JOB_NAME: self.job_name,
                },
            )

        job_names = await self.hass.async_add_executor_job(self.get_job_names)

        data_schema = vol.Schema({vol.Required(CONF_JOB_NAME): vol.In(job_names)})

        return self.async_show_form(step_id="job", data_schema=data_schema)

    def get_job_names(self):
        """Return the list of job names."""
        return [job[0] for job in self.server.get_jobs()]
