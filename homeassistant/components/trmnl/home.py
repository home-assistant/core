"""Send the picked entities to the TRMNL Home Assistant plugin."""

from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any

from aiohttp import ClientError
from trmnl.exceptions import TRMNLAuthenticationError, TRMNLError, TRMNLForbiddenError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import OAuth2TokenRequestReauthError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .const import LOGGER

PUSH_COOLDOWN_SECONDS = 90
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
                # Climate entities name their unit in temperature_unit.
                "unit": state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                or state.attributes.get("temperature_unit"),
                "attributes": {
                    key: state.attributes[key]
                    for key in SENT_ATTRIBUTES
                    if key in state.attributes
                },
            }
        )
    return {"areas": areas, "entities": entities}


class HomePusher:
    """Push the picked entities on start, and at most once every 90 seconds after they change."""

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
        self._unsubscribes: list[CALLBACK_TYPE] = []
        self._cancel_retry: CALLBACK_TYPE | None = None
        self._debouncer = Debouncer(
            hass,
            LOGGER,
            cooldown=PUSH_COOLDOWN_SECONDS,
            immediate=True,
            function=self._async_push,
        )

    @callback
    def async_start(self) -> None:
        """Push now, then after a picked entity, its device or its area changes."""
        bus = self._hass.bus
        self._unsubscribes = [
            async_track_state_change_event(
                self._hass, self._entity_ids, self._async_request_push
            ),
            bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                self._async_request_push,
                self._is_picked_entity,
            ),
            bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED,
                self._async_request_push,
                self._is_picked_device,
            ),
            bus.async_listen(
                ar.EVENT_AREA_REGISTRY_UPDATED,
                self._async_request_push,
                self._is_pushed_area,
            ),
        ]
        self._debouncer.async_schedule_call()

    async def async_stop(self) -> None:
        """Stop new pushes and wait for one under way, so its plugin id is saved."""
        for unsubscribe in self._unsubscribes:
            unsubscribe()
        self._cancel_pending_retry()
        self._debouncer.async_shutdown()
        async with self._debouncer.async_lock():
            pass

    @callback
    def _is_picked_entity(self, data: er.EventEntityRegistryUpdatedData) -> bool:
        return data["entity_id"] in self._entity_ids

    @callback
    def _is_picked_device(self, data: dr.EventDeviceRegistryUpdatedData) -> bool:
        """Return True for the device of a picked entity, or that device's parent."""
        entity_registry = er.async_get(self._hass)
        device_registry = dr.async_get(self._hass)
        return any(
            data["device_id"] in (device.id, getattr(device, "parent_device_id", None))
            for entity_id in self._entity_ids
            if (registry_entry := entity_registry.async_get(entity_id))
            and registry_entry.device_id
            and (device := device_registry.async_get(registry_entry.device_id))
        )

    @callback
    def _is_pushed_area(self, data: ar.EventAreaRegistryUpdatedData) -> bool:
        return (
            self._last_home is not None and data["area_id"] in self._last_home["areas"]
        )

    async def _async_push(self) -> None:
        # A pending retry holds every push until TRMNL's Retry-After has passed.
        if self._cancel_retry is not None:
            return
        home = build_home(self._hass, self._entity_ids)
        if home == self._last_home:
            return
        try:
            await self._push(home)
        except (
            OAuth2TokenRequestReauthError,
            TRMNLAuthenticationError,
            TRMNLForbiddenError,
        ):
            # Pushing again cannot work; the reload after reauth starts a new pusher.
            self._debouncer.async_shutdown()
            self._entry.async_start_reauth(self._hass)
            return
        except (TRMNLError, ClientError, TimeoutError) as err:
            if not self._failing:
                LOGGER.warning("Could not send the home to TRMNL: %s", err)
            self._failing = True
            retry_after = getattr(err, "retry_after", None) or PUSH_COOLDOWN_SECONDS
            self._cancel_retry = async_call_later(
                self._hass, retry_after, self._async_retry
            )
            return
        if self._failing:
            LOGGER.info("Sent the home to TRMNL again")
        self._failing = False
        self._last_home = home
        # The debouncer drops a change whose cooldown ended while this push ran.
        if build_home(self._hass, self._entity_ids) != home:
            self._debouncer.async_schedule_call()

    @callback
    def _cancel_pending_retry(self) -> None:
        if self._cancel_retry is not None:
            self._cancel_retry()
            self._cancel_retry = None

    @callback
    def _async_retry(self, _now: datetime) -> None:
        self._cancel_retry = None
        self._debouncer.async_schedule_call()

    @callback
    def _async_request_push(self, _event: Event[Any]) -> None:
        self._debouncer.async_schedule_call()
