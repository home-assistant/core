"""Google Report State implementation."""
import logging

from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.significant_change import create_checker

from .const import DOMAIN
from .error import SmartHomeError
from .helpers import AbstractConfig, GoogleEntity, async_get_entities

# Time to wait until the homegraph updates
# https://github.com/actions-on-google/smart-home-nodejs/issues/196#issuecomment-439156639
INITIAL_REPORT_DELAY = 60


_LOGGER = logging.getLogger(__name__)


@callback
def async_enable_report_state(hass: HomeAssistant, google_config: AbstractConfig):
    """Enable state reporting."""
    checker = None

    async def async_entity_state_listener(changed_entity, old_state, new_state):
        if not hass.is_running:
            return

        if not new_state:
            return

        if not google_config.should_expose(new_state):
            return

        entity = GoogleEntity(hass, google_config, new_state)

        if not entity.is_supported():
            return

        try:
            entity_data = entity.query_serialize()
        except SmartHomeError as err:
            _LOGGER.debug("Not reporting state for %s: %s", changed_entity, err.code)
            return

        if not checker.async_is_significant_change(new_state, extra_arg=entity_data):
            return

        _LOGGER.debug("Reporting state for %s: %s", changed_entity, entity_data)

        await google_config.async_report_state_all(
            {"devices": {"states": {changed_entity: entity_data}}}
        )

    @callback
    def extra_significant_check(
        hass: HomeAssistant,
        old_state: str,
        old_attrs: dict,
        old_extra_arg: dict,
        new_state: str,
        new_attrs: dict,
        new_extra_arg: dict,
    ):
        """Check if the serialized data has changed."""
        return old_extra_arg != new_extra_arg

    async def inital_report(_now):
        """Report initially all states."""
        nonlocal unsub, checker
        entities = {}

        checker = await create_checker(hass, DOMAIN, extra_significant_check)

        for entity in async_get_entities(hass, google_config):
            if not entity.should_expose():
                continue

            try:
                entity_data = entity.query_serialize()
            except SmartHomeError:
                continue

            # Tell our significant change checker that we're reporting
            # So it knows with subsequent changes what was already reported.
            if not checker.async_is_significant_change(
                entity.state, extra_arg=entity_data
            ):
                continue

            entities[entity.entity_id] = entity_data

        if not entities:
            return

        await google_config.async_report_state_all({"devices": {"states": entities}})

        unsub = hass.helpers.event.async_track_state_change(
            MATCH_ALL, async_entity_state_listener
        )

    unsub = async_call_later(hass, INITIAL_REPORT_DELAY, inital_report)

    # pylint: disable=unnecessary-lambda
    return lambda: unsub()
