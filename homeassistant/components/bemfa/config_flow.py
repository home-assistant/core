"""Config flow for bemfa integration."""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_INCLUDE_ENTITIES, CONF_UID, DOMAIN
from .entities_config import ENTITIES_CONFIG, FILTER
from .helper import generate_topic
from .http import BemfaHttp

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_UID): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for bemfa."""

    VERSION = 1

    _user_input: dict[str, Any] = {}
    _http: BemfaHttp
    _all_topics: dict[str, str]

    # Bemfa Service uses uid to auth api calls. One shall provide his uid to config this integration.
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, last_step=False
            )

        # uid should match this regExp
        if not re.match("^[0-9a-f]{32}$", user_input[CONF_UID]):
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "invalid_uid"},
                last_step=False,
            )

        # Multiply integration instances with same uid may case unexpected results.
        # We save the md5sum of each configured uid to self.hass.data[DOMAIN].
        # And check if this uid has been configured.
        if DOMAIN in self.hass.data:
            uid_md5 = hashlib.md5(user_input[CONF_UID].encode("utf-8")).hexdigest()
            for data in self.hass.data[DOMAIN].values():
                if data["uid_md5"] == uid_md5:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=STEP_USER_DATA_SCHEMA,
                        errors={"base": "duplicated_uid"},
                        last_step=False,
                    )

        self._user_input.update(user_input)
        return await self.async_step_entities()

    # Bemfa Service commuicates with devices by mqtt.
    # Each device corresponds to a particular topic whose suffix is a 3 digit number to indicate its type.
    # We guide one to sellect entities he wants to sync to Bemfa Service.
    # Then we make http calls to submit his selection.
    # At this moment, editing selection after configuration is not supported.
    # One may remove this integration and config again to achieve this.
    # When reconfiguring, entities selected last time will be checked by default.
    async def async_step_entities(self, user_input: dict[str, Any] | None = None):
        """Select entities."""
        if user_input is None:
            self._http = BemfaHttp(self.hass, self._user_input[CONF_UID])

            # fetch topics created by us before.
            self._all_topics = await self._http.async_fetch_all_topics()

            # filter entities we support
            entities = sorted(
                filter(
                    lambda item: FILTER not in ENTITIES_CONFIG[item.domain]
                    or ENTITIES_CONFIG[item.domain][FILTER](item.attributes),
                    self.hass.states.async_all(ENTITIES_CONFIG.keys()),
                ),
                key=lambda item: item.entity_id,
            )

            # find entities configured last time
            default = [
                entity.entity_id
                for entity in filter(
                    lambda ent: generate_topic(ent.domain, ent.entity_id)
                    in self._all_topics,
                    entities,
                )
            ]

            return self.async_show_form(
                step_id="entities",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_INCLUDE_ENTITIES,
                            default=default,
                        ): cv.multi_select(
                            {entity.entity_id: entity.name for entity in entities}
                        ),
                    }
                ),
                last_step=True,
            )

        #  start to sync selected entities to Bemfa Service
        for entity_id in user_input[CONF_INCLUDE_ENTITIES]:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            topic = generate_topic(state.domain, entity_id)

            if topic in self._all_topics:
                # topic has already been configured before, reuse it
                if self._all_topics[topic] != state.name:
                    await self._http.async_rename_topic(topic, state.name)

                # remove topic from self._all_topics when its entity is selected.
                # After the loop, topics remained in self._all_topics are to be removed.
                del self._all_topics[topic]
            else:
                # topic not configured before, create it
                await self._http.async_add_topic(topic, state.name)

        # remove the topics we do not need
        for topic in self._all_topics:
            await self._http.async_del_topic(topic)
        # end to sync

        self._user_input.update(user_input)
        entity_num = len(user_input[CONF_INCLUDE_ENTITIES])
        return self.async_create_entry(
            title=f"{self._user_input[CONF_UID][-10:]} ({entity_num})",
            data=self._user_input,
        )
