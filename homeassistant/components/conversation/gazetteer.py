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
from dataclasses import dataclass
from functools import partial
from typing import Any

from gazetteer_matcher import (
    FrameCandidate,
    GazetteerMatcher,
    Interpretation,
    TargetReference,
)
from gazetteer_matcher.config import MatcherConfig

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

DISPLAY_SLOTS = ("name", "area", "floor")
"""Slots carrying a registry id, which a response template would read out loud."""

TARGET_TAGS = frozenset({"area", "device_class", "domain", "floor", "name"})
"""Span tags that mean the matcher resolved something in the home."""


@callback
def async_refusal(interpretation: Interpretation) -> str | None:
    """Return wording for a refusal that says more than "I didn't understand".

    The matcher writes a response for every rejection, but most of them explain
    nothing, because noise resolves nothing: "asdfgh" and "do something" both come back
    as "Sorry, I don't know what action to take". Home Assistant's own error is the
    better answer there, not least because it is translated. It is only worth
    displacing when the matcher got as far as something in the home, and can say so.
    """
    if not interpretation.response:
        return None
    if not any(span.tag in TARGET_TAGS for span in interpretation.spans):
        return None
    return interpretation.response


@callback
def async_build_home(hass: HomeAssistant) -> dict[str, Any]:
    """Build the matcher's gazetteer of the home from the registries.

    The shape is the `home.yaml` gazetteer-matcher documents: areas and floors with
    their aliases, and every entity exposed to conversation with the names it answers
    to. Entities carry no floor of their own because the matcher takes an entity's floor
    from its area, which is the only way Home Assistant assigns one.
    """
    entity_registry = er.async_get(hass)

    floors = {
        floor.floor_id: {"name": floor.name, "aliases": list(floor.aliases)}
        for floor in fr.async_get(hass).async_list_floors()
    }
    areas = {
        area.id: {
            "name": area.name,
            "aliases": list(area.aliases),
            "floor": area.floor_id,
        }
        for area in ar.async_get(hass).async_list_areas()
    }

    entities: dict[str, dict[str, Any]] = {}
    for state in hass.states.async_all():
        if not async_should_expose(hass, DOMAIN, state.entity_id):
            continue

        entry = entity_registry.async_get(state.entity_id)
        names = _names(hass, state, entry)
        if not names:
            continue

        spec: dict[str, Any] = {
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


@dataclass(frozen=True)
class _ResponseKey:
    """One sentence block's response key, and the domains it was written for."""

    key: str
    domains: frozenset[str]

    def fits(self, domain: str | None) -> bool:
        """Return whether this key can answer for a target in `domain`."""
        return not self.domains or domain is None or domain in self.domains


class GazetteerResponses:
    """Which response answers a recognized frame.

    The matcher writes wording for refusals only, so a successful command is answered
    from the same intents data hassil was loaded from: each sentence block declares a
    response key alongside the slot combination the matcher validated against. The key
    is therefore a lookup on (intent, combination), narrowed by the target's domain
    where a combination spells several -- `HassTurnOn/domain_only` answers "Turned on
    the lights" for `light` and "Turned on the fans" for `fan`.
    """

    def __init__(self, intents_dict: dict[str, Any]) -> None:
        """Index the response key of every sentence block by the shape it answers."""
        keys: dict[tuple[str, str], list[_ResponseKey]] = {}
        for intent_name, intent_data in (intents_dict.get("intents") or {}).items():
            for block in (intent_data or {}).get("data") or []:
                response = block.get("response")
                combination = (block.get("metadata") or {}).get("slot_combination")
                if not response or not combination:
                    continue

                domains = _domains((block.get("slots") or {}).get("domain")) | _domains(
                    (block.get("requires_context") or {}).get("domain")
                )
                keys.setdefault((intent_name, str(combination)), []).append(
                    _ResponseKey(str(response), domains)
                )

        self._keys = {
            shape: tuple(dict.fromkeys(found)) for shape, found in keys.items()
        }

    def key_for(
        self, intent_name: str, combination: str, domain: str | None
    ) -> str | None:
        """Return the response key for a frame, or None to say nothing.

        A key written for a domain beats a generic one, and what is left has to be
        unanimous. The frame is everything the matcher knows about the sentence, so a
        shape the corpus answers two ways is one it cannot choose between: "are any
        lights on" and "how many lights are on" are both `HassGetState/domain_state`,
        and answering the second one "Yes" is worse than answering it silently.
        """
        candidates = self._keys.get((intent_name, combination), ())
        fitting = [key for key in candidates if key.fits(domain)]
        preferred = [key for key in fitting if key.domains] or fitting
        distinct = list(dict.fromkeys(key.key for key in preferred))
        return distinct[0] if len(distinct) == 1 else None


def _domains(block: Any) -> frozenset[str]:
    """Flatten however a domain list is written: one domain, a list, or tiers."""
    if not block:
        return frozenset()
    if isinstance(block, str):
        return frozenset([block])
    if isinstance(block, list):
        return frozenset(block)
    return frozenset(
        domain
        for value in block.values()
        for domain in (value if isinstance(value, list) else [value])
    )


class GazetteerFallback:
    """The matcher, kept in step with the home it resolves names against."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the fallback without loading anything yet."""
        self.hass = hass
        self._matcher: GazetteerMatcher | None = None
        self._build_lock = asyncio.Lock()

        # Data files, loaded once and reused by every rebuild.
        self._data: MatcherConfig | None = None

        # Kept past invalidation so a response can still name what it just acted on.
        self._home: dict[str, Any] = {}

        self._previous_targets: OrderedDict[str, tuple[TargetReference, ...]] = (
            OrderedDict()
        )

    @callback
    def async_invalidate(self) -> None:
        """Drop the home snapshot after a registry or exposure change."""
        self._matcher = None

    def supports(self, language: str) -> bool:
        """Return whether the matcher has a vocabulary for this language."""
        return language_util.Dialect.parse(language).language == LANGUAGE

    async def async_interpret(
        self,
        text: str,
        conversation_id: str,
        area: ar.AreaEntry | None,
    ) -> Interpretation:
        """Interpret text against the current home."""
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

        if result.accepted:
            # This turn is now the one a pronoun refers back to, whether or not it left
            # anything referrable behind: "them" should mean the command just given or
            # no command at all, never reach past it to an older one.
            self._previous_targets.pop(conversation_id, None)
            self._previous_targets[conversation_id] = result.targets
            while len(self._previous_targets) > _PREVIOUS_TARGETS_CAPACITY:
                self._previous_targets.popitem(last=False)

        return result

    async def _async_get_matcher(self) -> GazetteerMatcher:
        """Return the matcher, rebuilding it around a fresh home if needed."""
        if self._matcher is not None:
            return self._matcher

        async with self._build_lock:
            if self._matcher is None:
                home = async_build_home(self.hass)
                self._matcher = await self.hass.async_add_executor_job(
                    self._build_matcher, home
                )
                self._home = home

        return self._matcher

    def _build_matcher(self, home: dict[str, Any]) -> GazetteerMatcher:
        """Build a matcher over `home` (run inside executor).

        Only the home changes between rebuilds, so the vocabulary, intent catalog and
        refusal wording of the first matcher are handed to every one after it rather
        than being read off disk again.
        """
        if self._data is None:
            matcher = GazetteerMatcher(home=home)
            self._data = matcher.config
            return matcher

        return GazetteerMatcher(
            home=home,
            vocabulary=self._data.vocabulary,
            intents=self._data.intents,
            responses=self._data.responses,
        )

    @callback
    def async_intent_slots(self, frame: FrameCandidate) -> dict[str, Any]:
        """Return a frame's slots in the form intent handlers take.

        The values are the ids the matcher resolved -- `name` an entity id, `area` and
        `floor` their registry ids -- which Home Assistant matches by as readily as by
        name. The display name rides along as the slot's text, which is what the intent
        handler substitutes back in for the response template to speak.
        """
        return {
            slot: {"value": value, "text": self.async_display_text(slot, value)}
            for slot, value in frame.slots.items()
        }

    @callback
    def async_display_text(self, slot: str, value: Any) -> str:
        """Return what a response template should say for a slot value."""
        if slot in DISPLAY_SLOTS:
            collection = {"name": "entities", "area": "areas", "floor": "floors"}[slot]
            spec = (self._home.get(collection) or {}).get(str(value))
            if spec and spec.get("name"):
                return str(spec["name"])
        return str(value)

    @callback
    def async_domain(self, frame: FrameCandidate) -> str | None:
        """Return what a frame acts on, which picks between phrasings.

        A named target's own domain is the more specific answer, so it wins over the
        slot. A `domain` slot holding several is no answer at all.
        """
        if entity_id := frame.slots.get("name"):
            return str(entity_id).split(".", maxsplit=1)[0]

        domain = frame.slots.get("domain")
        if isinstance(domain, (list, tuple)):
            return str(domain[0]) if len(domain) == 1 else None
        return str(domain) if domain else None
