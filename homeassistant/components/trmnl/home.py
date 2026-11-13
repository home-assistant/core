"""Send the picked entities to the TRMNL Home Assistant plugin."""

from collections.abc import Callable, Coroutine
from typing import Any

from aiohttp import ClientError
from trmnl.exceptions import TRMNLError, TRMNLForbiddenError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import OAuth2TokenRequestReauthError
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_state_change_event

from .const import LOGGER

PUSH_COOLDOWN_SECONDS = 60
SENT_ATTRIBUTES = ("brightness", "current_temperature", "current_position")


def build_home(hass: HomeAssistant, entity_ids: list[str]) -> dict[str, Any]:
    """Return the picked entities and the names of their areas."""
    entity_registry = er.async_get(hass)
    area_registry = ar.async_get(hass)
    areas: dict[str, str] = {}
    entities: list[dict[str, Any]] = []
    for entity_id in entity_ids:
        if (state := hass.states.get(entity_id)) is None:
            continue
        registry_entry = entity_registry.async_get(entity_id)
        area_id = registry_entry and er.async_get_effective_area_id(
            hass, registry_entry
        )
        if area_id and (area := area_registry.async_get_area(area_id)):
            areas[area_id] = area.name
        entities.append(
            {
                "entity_id": entity_id,
                "name": state.name,
                "area_id": area_id,
                "domain": state.domain,
                "device_class": state.attributes.get(ATTR_DEVICE_CLASS),
                "state": state.state,
                "unit": state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
                "attributes": {
                    key: state.attributes[key]
                    for key in SENT_ATTRIBUTES
                    if key in state.attributes
                },
            }
        )
    return {"areas": areas, "entities": entities}


class HomePusher:
    """Push the picked entities on start and at most once a minute after they change."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        entity_ids: list[str],
        push: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Initialize the pusher."""
        self._hass = hass
        self._entry = entry
        self._entity_ids = entity_ids
        self._push = push
        self._last_home: dict[str, Any] | None = None
        self._failing = False
        self._unsubscribe: CALLBACK_TYPE | None = None
        self._debouncer = Debouncer(
            hass,
            LOGGER,
            cooldown=PUSH_COOLDOWN_SECONDS,
            immediate=True,
            function=self._async_push,
        )

    @callback
    def async_start(self) -> None:
        """Push now, then after changes."""
        self._unsubscribe = async_track_state_change_event(
            self._hass, self._entity_ids, self._async_state_changed
        )
        self._debouncer.async_schedule_call()

    async def async_stop(self) -> None:
        """Stop new pushes and wait for one under way, so its plugin id is saved."""
        if self._unsubscribe is not None:
            self._unsubscribe()
        self._debouncer.async_shutdown()
        async with self._debouncer.async_lock():
            pass

    async def _async_push(self) -> None:
        home = build_home(self._hass, self._entity_ids)
        if home == self._last_home:
            return
        try:
            await self._push(home)
        except OAuth2TokenRequestReauthError, TRMNLForbiddenError:
            # Pushing again cannot work; the reload after reauth starts a new pusher.
            self._debouncer.async_shutdown()
            self._entry.async_start_reauth(self._hass)
            return
        except (TRMNLError, ClientError, TimeoutError) as err:
            if not self._failing:
                LOGGER.warning("Could not send the home to TRMNL: %s", err)
            self._failing = True
            return
        if self._failing:
            LOGGER.info("Sent the home to TRMNL again")
        self._failing = False
        self._last_home = home

    @callback
    def _async_state_changed(self, _event: Event[EventStateChangedData]) -> None:
        self._debouncer.async_schedule_call()
