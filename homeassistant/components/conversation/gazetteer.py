"""Gazetteer intent matching for the default conversation agent.

hassil recognizes a sentence by template, so a phrasing it has no template for does not
match, and neither does one whose entity name was misheard. `gazetteer-matcher` reaches
the same intents a different way: it tags lexical spans against a gazetteer of the home,
builds candidate frames from them, and validates those frames against the
slot-combination catalog in `home-assistant-intents`. That covers wordings and near-miss
names hassil cannot, which is why it is worth running behind hassil.

Only behind hassil, and only when the default agent is answering on its own. With an LLM
configured and "prefer local intents" set, hassil is a fast path in front of that LLM,
and a sentence it declines is one the LLM is meant to get -- a second local recognizer
there would take work away from the better answer. That fast path is
`DefaultAgent.async_handle_intents`, which does not come through here.

The matcher itself is stateless, and this module owns the three things it therefore
cannot: the home it resolves names against, which response to speak once a command has
been handled, and what the previous turn targeted so "turn them back on" knows what to
do.
"""

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from functools import partial
from typing import Any

from gazetteer_matcher import (
    AreaSpec,
    EntitySpec,
    FloorSpec,
    FrameCandidate,
    GazetteerMatcher,
    Home,
    Interpretation,
    TargetReference,
)

from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import (
    area_registry as ar,
    chat_session,
    entity_registry as er,
    floor_registry as fr,
    intent,
)
from homeassistant.util import language as language_util

from .const import DOMAIN

LANGUAGE = "en"
"""The matcher ships an English vocabulary and nothing else."""


@callback
def async_refusal(interpretation: Interpretation) -> str | None:
    """Return wording for a refusal that says more than "I didn't understand"."""
    if not interpretation.refusal_target:
        return None
    return interpretation.response


_SENTENCE_END = (".", "!", "?")


def join_speech(parts: Sequence[str]) -> str:
    """Join what the frames of one coordinated command said into one answer."""
    sentences = [
        part if part.endswith(_SENTENCE_END) else f"{part}."
        for part in (part.strip() for part in parts)
        if part
    ]
    return " ".join(sentences)


@callback
def async_build_home(hass: HomeAssistant) -> Home:
    """Build the matcher's gazetteer of the home from the registries."""
    entity_registry = er.async_get(hass)

    floors: dict[str, FloorSpec] = {
        floor.floor_id: {"name": floor.name, "aliases": list(floor.aliases)}
        for floor in fr.async_get(hass).async_list_floors()
    }
    areas: dict[str, AreaSpec] = {
        area.id: {
            "name": area.name,
            "aliases": list(area.aliases),
            "floor": area.floor_id,
        }
        for area in ar.async_get(hass).async_list_areas()
    }

    entities: dict[str, EntitySpec] = {}
    for state in hass.states.async_all():
        if not async_should_expose(hass, DOMAIN, state.entity_id):
            continue

        entry = entity_registry.async_get(state.entity_id)
        names = _names(hass, state, entry)
        spec: EntitySpec = {
            "name": names[0],
            "aliases": names[1:],
            "domain": state.domain,
            "area": (
                er.async_get_effective_area_id(hass, entry)
                if entry is not None
                else None
            ),
        }
        if device_class := state.attributes.get(ATTR_DEVICE_CLASS):
            spec["device_class"] = device_class
        entities[state.entity_id] = spec

    return {"areas": areas, "floors": floors, "entities": entities}


@callback
def _names(
    hass: HomeAssistant, state: State, entry: er.RegistryEntry | None
) -> list[str]:
    """Every name an entity answers to, the displayed one first."""
    seen: set[str] = set()
    names: list[str] = []
    for name in (
        state.name,
        *intent.async_get_entity_aliases(hass, entry, state=state),
    ):
        name = " ".join(name.split())
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            names.append(name)
    return names


_TARGET_SCOPES = (
    (intent.IntentResponseTargetType.FLOOR, TargetReference.for_floor),
    (intent.IntentResponseTargetType.AREA, TargetReference.for_area),
    (intent.IntentResponseTargetType.ENTITY, TargetReference.for_entity),
)
"""Target kinds a pronoun can refer back to, widest selector first.

"turn them off" after "turn on the kitchen lights" means the kitchen lights, not the
one entity that happened to match, so the area the sentence named wins over what it
resolved to.
"""


@callback
def async_targets_from_intent(
    slots: dict[str, Any], intent_response: intent.IntentResponse
) -> tuple[TargetReference, ...]:
    """Return what a sentence hassil recognized selected, for a later "it"/"them"."""
    resolved: dict[str, list[str]] = {}
    for target in intent_response.success_results:
        if target.id:
            resolved.setdefault(target.type, []).append(target.id)

    # Carried alongside the selector, as the matcher's own targets carry them: "turn
    # them off" should mean the lights it was just told about, not the whole area.
    values = {
        slot: slots[slot]["value"]
        for slot in ("domain", "device_class")
        if slot in slots
    }

    for target_type, build in _TARGET_SCOPES:
        ids = resolved.get(target_type)
        if not ids:
            continue
        if len(ids) > 1:
            # Several rooms, or several entities named at once: nothing a pronoun
            # picks out, and the matcher only reuses a single selector.
            return ()
        return (build(ids[0], **values),)

    return ()


async def _run_uninterrupted[_T](future: asyncio.Future[_T]) -> _T:
    """Await an executor job without returning before its thread stops.

    Cancelling an await on `run_in_executor` does not interrupt the worker, so a
    cancelled request would leave the lock around the call while the thread was
    still inside the matcher -- which is the overlap the lock exists to prevent.
    The caller is still cancelled; it just does not get to run ahead of the work.
    """
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        await asyncio.wait([future])
        raise


class _HomeLock:
    """Many interpretations at once, or one rebuild, never both.

    `set_home` swaps the tagger and the gazetteer under a matcher that other requests
    may be reading from an executor thread. Interpreting is read-only, so any number
    can run together; rebuilding needs the matcher to itself.

    A waiting rebuild also holds off new interpretations, so a steady stream of
    utterances cannot leave the home stale indefinitely. Rebuilds only follow registry
    changes, so there is no matching risk the other way.
    """

    def __init__(self) -> None:
        """Initialize with nothing held."""
        self._condition = asyncio.Condition()
        self._readers = 0
        self._writing = False
        self._writers_waiting = 0

    @asynccontextmanager
    async def read(self) -> AsyncIterator[None]:
        """Hold off a rebuild for as long as this interpretation runs."""
        async with self._condition:
            await self._condition.wait_for(
                lambda: not self._writing and not self._writers_waiting
            )
            self._readers += 1
        try:
            yield
        finally:
            async with self._condition:
                self._readers -= 1
                if not self._readers:
                    self._condition.notify_all()

    @asynccontextmanager
    async def write(self) -> AsyncIterator[None]:
        """Take the matcher exclusively, once the interpretations in flight finish."""
        async with self._condition:
            self._writers_waiting += 1
            try:
                await self._condition.wait_for(
                    lambda: not self._writing and not self._readers
                )
            except BaseException:
                # Giving up while queued, most likely cancelled. Readers are held
                # off by the count of waiting writers, so they all become free at
                # once. `Condition.wait` wakes one of them on the way out of a
                # cancelled wait, which is enough to avoid a stall but leaves the
                # rest asleep until that one finishes; wake them together instead.
                self._writers_waiting -= 1
                self._condition.notify_all()
                raise
            self._writers_waiting -= 1
            self._writing = True
        try:
            yield
        finally:
            async with self._condition:
                self._writing = False
                self._condition.notify_all()


class GazetteerFallback:
    """The matcher, kept in step with the home it resolves names against."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the fallback without loading anything yet."""
        self.hass = hass
        self._matcher: GazetteerMatcher | None = None
        self._lock = _HomeLock()
        self._stale = False
        self._previous_targets: dict[str, tuple[TargetReference, ...]] = {}

    @callback
    def async_invalidate(self) -> None:
        """Note that a registry or exposure change has outdated the home."""
        self._stale = True

    def supports(self, language: str) -> bool:
        """Return whether the matcher has a vocabulary for this language."""
        return language_util.Dialect.parse(language).language == LANGUAGE

    async def async_interpret(
        self,
        text: str,
        conversation_id: str,
        area: ar.AreaEntry | None,
    ) -> tuple[GazetteerMatcher, Interpretation]:
        """Interpret text, returning it with the matcher that read it.

        The matcher is settled before the read lock is taken rather than under it,
        because a rebuild needs the lock exclusively and no lock can be upgraded.
        A rebuild that starts in between simply runs first; this then interprets
        against its result, which is newer than expected but never half-swapped.
        """
        matcher = await self._async_get_matcher()
        interpret = partial(
            matcher.interpret,
            text,
            previous_targets=self._previous_targets.get(conversation_id, ()),
        )

        async with self._lock.read():
            try:
                result = await _run_uninterrupted(
                    self.hass.async_add_executor_job(
                        partial(
                            interpret,
                            context_area=area.id if area else None,
                            context_floor=area.floor_id if area else None,
                        )
                    )
                )
            except ValueError:
                # The registries moved on from the snapshot mid-request. The sentence
                # is still worth trying unplaced; shapes needing a room refuse anyway.
                result = await _run_uninterrupted(
                    self.hass.async_add_executor_job(interpret)
                )

        return matcher, result

    @callback
    def async_remember(
        self, conversation_id: str, targets: Sequence[TargetReference] = ()
    ) -> None:
        """Make this turn the one a pronoun refers back to (it/them).

        What a conversation was about lasts exactly as long as the conversation: the
        entry is dropped when its chat session is cleaned up. Bounding the number of
        conversations instead would let a house busy enough to hold several at once
        take the antecedent away from whoever spoke least recently, however lately
        they spoke.
        """
        if conversation_id not in self._previous_targets:
            session = chat_session.current_session.get()
            if session is None:
                # Nothing would ever clean this up, so do not start it.
                return
            session.async_on_cleanup(partial(self.async_forget, conversation_id))

        self._previous_targets[conversation_id] = tuple(targets)

    @callback
    def async_forget(self, conversation_id: str) -> None:
        """Drop what a conversation was about, once it is over."""
        self._previous_targets.pop(conversation_id, None)

    async def _async_get_matcher(self) -> GazetteerMatcher:
        """Return the matcher, over a home built or refreshed from the registries.

        Reading the registries has to happen here, since that is where they are safe
        to touch, but it is only assembling a dictionary. Building the tagger around
        that dictionary is the expensive half and grows with the home -- tens of
        milliseconds at a few hundred entities, and a fifth of a second at a few
        thousand -- so it goes to the executor whether the matcher is new or not.
        """
        if self._matcher is not None and not self._stale:
            # Nothing to do, and taking the lock would shut out other interpretations.
            return self._matcher

        async with self._lock.write():
            # Cleared before the home is read, so a registry change arriving while
            # this rebuilds sets it again rather than being erased on the way out.
            stale, self._stale = self._stale, False

            try:
                if self._matcher is None:
                    self._matcher = await _run_uninterrupted(
                        self.hass.async_add_executor_job(
                            partial(GazetteerMatcher, home=async_build_home(self.hass))
                        )
                    )
                elif stale:
                    await _run_uninterrupted(
                        self.hass.async_add_executor_job(
                            self._matcher.set_home, async_build_home(self.hass)
                        )
                    )
            except BaseException:
                # Whatever went wrong, the home on the matcher is not the one that
                # was asked for. Leaving the flag clear would strand it there until
                # something unrelated changed.
                self._stale = True
                raise

        return self._matcher

    @callback
    def async_intent_slots(
        self, matcher: GazetteerMatcher, frame: FrameCandidate
    ) -> dict[str, Any]:
        """Return a frame's slots in the form intent handlers take."""
        return {
            slot: {"value": value, "text": matcher.display_name(slot, value)}
            for slot, value in frame.slots.items()
        }
