"""Gazetteer intent matching for the default conversation agent.

hassil recognizes a sentence by template, so a phrasing it has no template for does
not match, and neither does one whose entity name was misheard. gazetteer-matcher
reaches the same intents by tagging spans against a gazetteer of the home, which
covers wordings and near-miss names hassil cannot.

It runs behind hassil, and only when the default agent is answering on its own.
With "prefer local intents" set, hassil is a fast path in front of an LLM and a
sentence it declines is one the LLM is meant to get, so that path
(`DefaultAgent.async_handle_intents`) does not come through here.
"""

import asyncio
from collections.abc import Sequence
from functools import partial
from typing import Any

from gazetteer_matcher import (
    AreaSpec,
    EntitySpec,
    FloorSpec,
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

_SENTENCE_END = (".", "!", "?")

_ANAPHORA_PREFIX = "anaphora"

# Widest selector first: "turn them off" after "turn on the kitchen lights" means
# the kitchen lights, not the one entity that happened to match.
_TARGET_SCOPES = (
    (intent.IntentResponseTargetType.FLOOR, TargetReference.for_floor),
    (intent.IntentResponseTargetType.AREA, TargetReference.for_area),
    (intent.IntentResponseTargetType.ENTITY, TargetReference.for_entity),
)


@callback
def async_refers_back(interpretation: Interpretation) -> bool:
    """Return whether the matcher read the sentence as a follow-up ("it"/"them")."""
    if (interpretation.rejection_code or "").startswith(_ANAPHORA_PREFIX):
        return True
    return any(
        candidate.anaphor_target is not None
        for segment in interpretation.segments
        for candidate in segment.frame_candidates
    )


@callback
def async_refusal(interpretation: Interpretation) -> str | None:
    """Return the matcher's wording for a refusal that explains itself."""
    if not interpretation.refusal_target and not async_refers_back(interpretation):
        return None
    return interpretation.response


def join_speech(parts: Sequence[str]) -> str:
    """Join the answers of one coordinated command into one thing to speak."""
    seen: set[str] = set()
    sentences: list[str] = []
    for part in (part.strip() for part in parts):
        if not part:
            continue
        sentence = part if part.endswith(_SENTENCE_END) else f"{part}."
        # A follow-up answers for every target it reached, in the same words.
        if sentence in seen:
            continue
        seen.add(sentence)
        sentences.append(sentence)

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
        if not (names := _names(hass, state, entry)):
            continue

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
    """Return the names an entity answers to, without duplicates."""
    seen: set[str] = set()
    names: list[str] = []
    for name in intent.async_get_entity_aliases(hass, entry, state=state):
        name = " ".join(name.split())
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            names.append(name)
    return names


@callback
def async_targets_from_intent(
    slots: dict[str, Any], intent_response: intent.IntentResponse
) -> tuple[TargetReference, ...]:
    """Return what a sentence hassil recognized selected, for a later "it"/"them".

    The matcher resolves a follow-up pronoun only against targets it is handed, and
    hassil answers most sentences without reaching it, so the turn that named the
    thing has to be recorded from there too.
    """
    resolved: dict[str, list[str]] = {}
    for target in intent_response.success_results:
        if target.id:
            resolved.setdefault(target.type, []).append(target.id)

    # Carried alongside the selector: "turn them off" should mean the lights it was
    # just told about, not everything in the area.
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
            # Nothing a pronoun picks out, and the matcher reuses one selector.
            return ()
        return (build(ids[0], **values),)

    return ()


class GazetteerFallback:
    """The matcher, kept in step with the home it resolves names against."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the fallback without loading anything yet."""
        self.hass = hass
        self._matcher: GazetteerMatcher | None = None
        self._build_lock = asyncio.Lock()
        self._wanted_home = 0
        self._built_home = 0
        self._previous_targets: dict[str, tuple[TargetReference, ...]] = {}

    @callback
    def async_invalidate(self) -> None:
        """Note that a registry or exposure change has outdated the home."""
        self._wanted_home += 1

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

        The matcher comes back because answering needs it too, to name what the
        frames resolved. A rebuild replaces the matcher rather than changing it, so
        the one handed back keeps describing what was acted on.
        """
        matcher = await self._async_get_matcher()
        interpret = partial(
            matcher.interpret,
            text,
            previous_targets=self._previous_targets.get(conversation_id, ()),
        )

        try:
            result = await self.hass.async_add_executor_job(
                partial(interpret, context_area=area.id if area else None)
            )
        except ValueError:
            # The registries moved on from the snapshot mid-request. The sentence is
            # still worth trying unplaced; shapes needing a room refuse anyway.
            result = await self.hass.async_add_executor_job(interpret)

        return matcher, result

    @callback
    def async_remember(
        self, conversation_id: str, targets: Sequence[TargetReference] = ()
    ) -> None:
        """Make this turn the one a pronoun refers back to (it/them).

        The entry is dropped when its chat session is cleaned up, so what a
        conversation was about lasts exactly as long as the conversation.
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
        """Return the matcher, rebuilt from the registries if the home has changed."""
        if self._matcher is not None and self._built_home == self._wanted_home:
            return self._matcher

        async with self._build_lock:
            if self._matcher is not None and self._built_home == self._wanted_home:
                return self._matcher

            # Noted before the home is read, so a change arriving during the build
            # leaves the result behind rather than counting as current.
            building = self._wanted_home
            self._matcher = await self.hass.async_add_executor_job(
                _build_matcher, self._matcher, async_build_home(self.hass)
            )
            self._built_home = building

        return self._matcher


def _build_matcher(previous: GazetteerMatcher | None, home: Home) -> GazetteerMatcher:
    """Build a matcher over a home, reusing the data files of the last one.

    A new matcher rather than a change to the old one, so a request already reading
    from that one is unaffected and no locking is needed around either.
    """
    if previous is None:
        return GazetteerMatcher(home=home)

    config = previous.config
    return GazetteerMatcher(
        home=home,
        vocabulary=config.vocabulary,
        intents=config.intents,
        responses=config.responses,
    )
