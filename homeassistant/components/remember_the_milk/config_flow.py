from typing import Any

from homeassistant.components.remember_the_milk import DOMAIN, RTM_SCHEMA
from homeassistant.components.remember_the_milk.const import (
    CONF_SHARED_SECRET,
    RTM_TOKEN_SCHEMA,
)
from homeassistant.components.remember_the_milk.todo import RememberTheMilkCoordinator
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_TOKEN


class RememberTheMilkConfigFlow(ConfigFlow, domain=DOMAIN):
    coordinator: RememberTheMilkCoordinator | None = None

    def __init__(self) -> None:
        # TODO karel: use fields instead of a dict
        self.data = {}
        self.coordinator = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=RTM_SCHEMA, errors={}
            )

        name = self.data[CONF_NAME] = user_input[CONF_NAME]
        api_key = self.data[CONF_API_KEY] = user_input[CONF_API_KEY]
        shared_secret = self.data[CONF_SHARED_SECRET] = user_input[CONF_SHARED_SECRET]

        self.coordinator = RememberTheMilkCoordinator(name, api_key, shared_secret)

        # TODO: separate commit for (global) typo fix 'coordindator'
        token_valid = await self.hass.async_add_executor_job(
            self.coordinator.check_token
        )

        if not token_valid:
            url, frob = await self.hass.async_add_executor_job(
                self.coordinator.authenticate_desktop
            )
            self.data["frob"] = frob
            return self.async_show_form(
                step_id="token",
                last_step=True,
                data_schema=RTM_TOKEN_SCHEMA,
                # Showing an arbitrary field just so we can show the url in the error field is very silly but the best I could ind
                errors={
                    "dummy_field": f"Please visit {url} and come back here to complete the configuration."
                },
            )

        return self.create_entry()

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        def get_token():
            return self.coordinator.get_token(self.data["frob"])

        token = await self.hass.async_add_executor_job(get_token)
        self.data[CONF_TOKEN] = token
        return self.create_entry()

    # TODO: return type must be ConfigFlowResult
    def create_entry(self):
        name = self.data[CONF_NAME]
        api_key = self.data[CONF_API_KEY]
        shared_secret = self.data[CONF_SHARED_SECRET]
        token = self.data[CONF_TOKEN]
        return self.async_create_entry(  # TODO karel: slightly confused why this method is called async_... when it doesn't look like it's async
            title=name,
            data=dict(
                name=name, api_key=api_key, shared_secret=shared_secret, token=token
            ),
            description=f"Remember The Milk - {name}",
            description_placeholders=None,
            options=None,
        )
