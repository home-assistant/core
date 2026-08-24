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
been handled, and what the previous turn targeted so "turn them back on" has an it.
"""

import asyncio
from collections import OrderedDict
from collections.abc import Sequence
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
    entity_registry as er,
    floor_registry as fr,
    intent,
)
from homeassistant.util import language as language_util

from .const import DOMAIN

LANGUAGE = "en"
"""The matcher ships an English vocabulary and nothing else."""

_PREVIOUS_TARGETS_CAPACITY = 8
"""Conversations whose targets stay referrable.

No expiry to go with it: Home Assistant retires a conversation id after
`chat_session.CONVERSATION_TIMEOUT` and issues a fresh one, so an entry old enough to be
stale is one that will never be asked for again.
"""


@callback
def async_refusal(interpretation: Interpretation) -> str | None:
    """Return wording for a refusal that says more than "I didn't understand".

    The matcher writes a response for every rejection, but most of them explain
    nothing, because noise resolves nothing: "asdfgh" and "do something" both come back
    as "Sorry, I don't know what action to take". Home Assistant's own error is the
    better answer there, not least because it is translated. It is only worth
    displacing when the matcher named what it was aimed at.
    """
    if not interpretation.refusal_target:
        return None
    return interpretation.response


@callback
def async_build_home(hass: HomeAssistant) -> Home:
    """Build the matcher's gazetteer of the home from the registries.

    The shape is the `home.yaml` gazetteer-matcher documents: areas and floors with
    their aliases, and every entity exposed to conversation with the names it answers
    to. Entities carry no floor of their own because the matcher takes an entity's floor
    from its area, which is the only way Home Assistant assigns one.
    """
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
        if not names:
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
    """Every name an entity answers to, the displayed one first.

    The displayed name is the whole name and the only base name taken: a registry
    `name`/`original_name` may have had its device prefix stripped, and registering the
    remaining "Blinds" would let a bare device-class word capture commands meant for
    every blind in the house.
    """
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
    """Return what a sentence hassil recognized selected, for a later "it"/"them".

    The matcher is stateless: it resolves a follow-up pronoun only against targets it
    is handed. hassil answers most sentences and never reaches the matcher, so without
    this the turn that named the thing goes by unseen and "open it" has no antecedent.

    A handled intent reports what it acted on as typed, id-bearing results, which is
    the same selector shape the matcher builds from its own frames.
    """
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


class GazetteerFallback:
    """The matcher, kept in step with the home it resolves names against."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the fallback without loading anything yet."""
        self.hass = hass
        self._matcher: GazetteerMatcher | None = None
        self._build_lock = asyncio.Lock()
        self._stale = False
        self._previous_targets: OrderedDict[str, tuple[TargetReference, ...]] = (
            OrderedDict()
        )

    @callback
    def async_invalidate(self) -> None:
        """Note that a registry or exposure change has outdated the home.

        Rebuilt on the next use rather than now, since most changes are not followed
        by a sentence the matcher ever sees.
        """
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

        The matcher comes back because answering needs it too, to name what the frames
        resolved. Handing back the one that produced them means a home swapped in
        between still describes the entity that was actually acted on.
        """
        matcher = await self._async_get_matcher()
        interpret = partial(
            matcher.interpret,
            text,
            previous_targets=self._previous_targets.get(conversation_id, ()),
        )

        try:
            result = await self.hass.async_add_executor_job(
                partial(
                    interpret,
                    context_area=area.id if area else None,
                    context_floor=area.floor_id if area else None,
                )
            )
        except ValueError:
            # The registries moved on from the snapshot mid-request. The sentence is
            # still worth trying unplaced; the shapes needing a room refuse on their own.
            result = await self.hass.async_add_executor_job(interpret)

        return matcher, result

    @callback
    def async_remember(
        self, conversation_id: str, targets: Sequence[TargetReference] = ()
    ) -> None:
        """Make this turn the one a pronoun refers back to.

        Every turn that succeeded replaces the one before it, including a turn with
        nothing referrable in it: "it" should mean the command just given or no command
        at all, never reach past it to an older one that is still in the cache. A turn
        that failed leaves the entry alone, so "mumble" between two commands does not
        strand the pronoun after it.
        """
        self._previous_targets.pop(conversation_id, None)
        self._previous_targets[conversation_id] = tuple(targets)
        while len(self._previous_targets) > _PREVIOUS_TARGETS_CAPACITY:
            self._previous_targets.popitem(last=False)

    async def _async_get_matcher(self) -> GazetteerMatcher:
        """Return the matcher, over a home built or refreshed from the registries.

        Building the first one reads the matcher's data files and spells every number
        in the language, so it goes to the executor. Swapping the home afterwards
        touches neither and is fast enough to do here.
        """
        async with self._build_lock:
            if self._matcher is None:
                self._matcher = await self.hass.async_add_executor_job(
                    partial(GazetteerMatcher, home=async_build_home(self.hass))
                )
            elif self._stale:
                self._matcher.set_home(async_build_home(self.hass))
            self._stale = False

        return self._matcher

    @callback
    def async_intent_slots(
        self, matcher: GazetteerMatcher, frame: FrameCandidate
    ) -> dict[str, Any]:
        """Return a frame's slots in the form intent handlers take.

        The values are the ids the matcher resolved -- `name` an entity id, `area` and
        `floor` their registry ids -- which Home Assistant matches by as readily as by
        name. The display name rides along as the slot's text, which is what the intent
        handler substitutes back in for the response template to speak.
        """
        return {
            slot: {"value": value, "text": matcher.display_name(slot, value)}
            for slot, value in frame.slots.items()
        }
