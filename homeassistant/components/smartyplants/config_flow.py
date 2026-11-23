"""Config flow for SmartyPlants — this is what replaces configuration.yaml."""

from collections.abc import Mapping
from typing import Any, override

import probatio
from pysmartyplants import (
    SmartyPlantsAuthError,
    SmartyPlantsClient,
    SmartyPlantsConnectionError,
    SmartyPlantsForbiddenError,
)

from homeassistant.components import webhook as hass_webhook
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_WEBHOOK_ID
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_WEBHOOK_SECRET, DOMAIN
from .coordinator import SmartyPlantsConfigEntry

SECRET_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

CREDENTIALS_SCHEMA = probatio.Schema({probatio.Required(CONF_API_KEY): SECRET_SELECTOR})


# Optional: without a secret the integration polls and registers no webhook.
STEP_WEBHOOK_SCHEMA = probatio.Schema(
    {probatio.Optional(CONF_WEBHOOK_SECRET): SECRET_SELECTOR}
)

RECONFIGURE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_API_KEY): SECRET_SELECTOR,
        probatio.Optional(CONF_WEBHOOK_SECRET): SECRET_SELECTOR,
    }
)


class SmartyPlantsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup dialog."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow state."""
        self._data: dict[str, Any] = {}

    async def _async_validate(self, api_key: str) -> tuple[str | None, str | None]:
        """Return (error key, account id); exactly one is set."""
        client = SmartyPlantsClient(api_key, session=async_get_clientsession(self.hass))
        try:
            account_id = await client.async_verify()
        except SmartyPlantsAuthError:
            return "invalid_auth", None
        except SmartyPlantsForbiddenError:
            # The key is accepted but this caller is not allowed to use it,
            # which a different key will not fix.
            return "forbidden", None
        except SmartyPlantsConnectionError:
            return "cannot_connect", None
        return None, account_id

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt for the API key, then verify it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error, account_id = await self._async_validate(user_input[CONF_API_KEY])
            if error:
                errors["base"] = error
            else:
                # Keyed on the account, not the API key: a rotated key is the
                # same account and must not create a second entry.
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_configured()

                self._data = {
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_WEBHOOK_ID: hass_webhook.async_generate_id(),
                }
                return await self.async_step_webhook()

        return self.async_show_form(
            step_id="user",
            data_schema=CREDENTIALS_SCHEMA,
            errors=errors,
        )

    async def async_step_webhook(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the push URL and collect the signing secret.

        The backend's webhook endpoints are user-authenticated rather than
        API-key authenticated, so Home Assistant cannot register itself. The
        user pastes this URL into the SmartyPlants app, which hands back the
        secret they enter here.
        """
        if user_input is not None:
            secret = user_input.get(CONF_WEBHOOK_SECRET)
            return self.async_create_entry(
                title="SmartyPlants",
                data={
                    **self._data,
                    **({CONF_WEBHOOK_SECRET: secret} if secret else {}),
                },
            )

        try:
            # SmartyPlants calls this from the internet, so an internal
            # address would be useless to paste into the app.
            webhook_url = hass_webhook.async_generate_url(
                self.hass, self._data[CONF_WEBHOOK_ID], allow_internal=False
            )
        except NoURLAvailableError:
            # Without a reachable address there is nothing to offer, so the
            # entry is created and readings arrive on the poll instead.
            return self.async_create_entry(title="SmartyPlants", data=self._data)

        return self.async_show_form(
            step_id="webhook",
            data_schema=STEP_WEBHOOK_SCHEMA,
            description_placeholders={"webhook_url": webhook_url},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the API key, and the secret when the entry has a webhook."""
        entry = self._get_reconfigure_entry()
        if entry.data.get(CONF_WEBHOOK_ID) is None:
            # No webhook was ever set up, so there is no secret to collect.
            return await self.async_step_reconfigure_key(user_input)

        if (webhook_url := self._webhook_url(entry)) is None:
            # The endpoint stays registered whether or not an address can be
            # worked out, so the secret is still worth collecting.
            return await self.async_step_reconfigure_secret(user_input)

        return await self._async_reconfigure(
            user_input,
            step_id="reconfigure",
            data_schema=RECONFIGURE_SCHEMA,
            collects_secret=True,
            description_placeholders={"webhook_url": webhook_url},
        )

    async def async_step_reconfigure_secret(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the key or the secret, with no URL to show alongside it."""
        return await self._async_reconfigure(
            user_input,
            step_id="reconfigure_secret",
            data_schema=RECONFIGURE_SCHEMA,
            collects_secret=True,
        )

    async def async_step_reconfigure_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change only the API key, for an entry that has no webhook."""
        return await self._async_reconfigure(
            user_input,
            step_id="reconfigure_key",
            data_schema=CREDENTIALS_SCHEMA,
            collects_secret=False,
        )

    def _webhook_url(self, entry: SmartyPlantsConfigEntry) -> str | None:
        """Return the push URL for this entry, when there is one to show."""
        try:
            return hass_webhook.async_generate_url(
                self.hass, entry.data[CONF_WEBHOOK_ID], allow_internal=False
            )
        except NoURLAvailableError:
            return None

    async def _async_reconfigure(
        self,
        user_input: dict[str, Any] | None,
        *,
        step_id: str,
        data_schema: probatio.Schema,
        collects_secret: bool,
        description_placeholders: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Verify the key offered and store it, keeping the rest of the entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            error, account_id = await self._async_validate(user_input[CONF_API_KEY])
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_mismatch()

                data = {**entry.data, CONF_API_KEY: user_input[CONF_API_KEY]}
                # The webhook id is left alone: it is the URL already sitting
                # in the user's SmartyPlants app.
                if secret := user_input.get(CONF_WEBHOOK_SECRET):
                    data[CONF_WEBHOOK_SECRET] = secret
                elif collects_secret:
                    # Only an emptied field means the user is turning push off.
                    data.pop(CONF_WEBHOOK_SECRET, None)
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(data_schema, entry.data),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a rejected API key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt for a new API key for the same account."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error, account_id = await self._async_validate(user_input[CONF_API_KEY])
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=CREDENTIALS_SCHEMA,
            errors=errors,
        )
