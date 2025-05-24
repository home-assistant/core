"""Config flow for Blue Current integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bluecurrent_api import Client
from bluecurrent_api.exceptions import (
    AlreadyConnected,
    InvalidApiToken,
    RequestLimitReached,
    WebsocketError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_ID, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import BlueCurrentConfigEntry, Connector
from .const import BCU_APP, CARD, DOMAIN, LOGGER, WITHOUT_CHARGE_CARD

DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_TOKEN): str})


class BlueCurrentConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Blue Current."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            client = Client()
            api_token = user_input[CONF_API_TOKEN]

            try:
                customer_id = await client.validate_api_token(api_token)
                email = await client.get_email()
            except WebsocketError:
                errors["base"] = "cannot_connect"
            except RequestLimitReached:
                errors["base"] = "limit_reached"
            except AlreadyConnected:
                errors["base"] = "already_connected"
            except InvalidApiToken:
                errors["base"] = "invalid_token"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.source != SOURCE_REAUTH:
                    await self.async_set_unique_id(customer_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=email, data=user_input)

                reauth_entry = self._get_reauth_entry()
                if reauth_entry.unique_id == customer_id:
                    return self.async_update_reload_and_abort(
                        reauth_entry, data=user_input
                    )

                return self.async_abort(
                    reason="wrong_account",
                    description_placeholders={"email": email},
                )
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: BlueCurrentConfigEntry,
    ) -> ChargeCardsFlowHandler:
        """Get the options flow for Blue Current."""
        return ChargeCardsFlowHandler()


class ChargeCardsFlowHandler(config_entries.OptionsFlow):
    """Handle the options flow for Blue Current."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the card step."""

        connector: Connector = self.config_entry.runtime_data
        await connector.client.get_charge_cards()

        def card_display_name(card: dict[str, Any]) -> str:
            """Get the display name of a card. When the card has a name, show the name with the card id. Otherwise, only show the card id."""
            if card[CONF_ID] == BCU_APP:
                return WITHOUT_CHARGE_CARD
            if card[CONF_NAME] == "":
                return str(card[CONF_ID])
            return f"{card[CONF_NAME]} ({card[CONF_ID]})"

        def get_card_id(card_name: str) -> str:
            """Get the card id based on the display name."""
            split = card_name.rsplit("(")
            if len(split) == 1:
                if split[0] == WITHOUT_CHARGE_CARD:
                    return BCU_APP
                return split[0]
            return split[-1].strip(")")

        cards = [card_display_name(card) for card in connector.charge_cards.values()]

        current_charge_card_id = card_display_name(connector.selected_charge_card)

        card_schema = vol.Schema(
            {
                vol.Required(CARD, default=current_charge_card_id): SelectSelector(
                    SelectSelectorConfig(
                        options=cards,
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="select_charge_card",
                    )
                )
            }
        )

        if user_input is not None:
            selected_card = list(
                filter(
                    lambda card: card[CONF_ID] == get_card_id(user_input[CARD]),
                    connector.charge_cards.values(),
                )
            )[0]

            user_input[CARD] = selected_card
            return self.async_create_entry(title=CARD, data=user_input)

        return self.async_show_form(step_id="init", data_schema=card_schema)
