"""Repairs for the Hikvision integration."""

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    OperationNotAllowed,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN
from .identity import (
    async_earlier_devices,
    async_earlier_entities,
    async_link_to_kept_devices,
    async_move_device,
    decode_ambiguous_identities,
)

CONF_KEEP = "keep"


@dataclass(frozen=True, slots=True)
class _Groups:
    """The entry's earlier devices and entities, grouped once per pass.

    Each answer only moves the copies of its own group, so one pass can use them
    all without reading the registries again for each answer.
    """

    devices: dict[str, list[tuple[dr.DeviceEntry, tuple[str, str]]]]
    entities: dict[tuple[str, str], list[er.RegistryEntry]]

    @classmethod
    def read(cls, hass: HomeAssistant, entry: ConfigEntry) -> _Groups:
        """Group the earlier devices and entities of the entry as they are now."""
        device_id = str(entry.unique_id)
        return cls(
            async_earlier_devices(hass, entry, device_id),
            async_earlier_entities(hass, entry, device_id),
        )


# ("device", rest of the identifier) or ("entity", platform, rest of the unique ID)
type _Question = tuple[str, ...]


class AmbiguousIdentitiesRepairFlow(RepairsFlow):
    """Ask which of the earlier devices and entities of a camera to keep.

    Nothing changes until every question is answered, so a repair left halfway
    changes nothing and its issue stays. The answers are then applied together,
    the devices first, and the entry is reloaded once.
    """

    def __init__(
        self,
        issue_id: str,
        entry_id: str,
        devices: list[str],
        entities: list[list[str]],
    ) -> None:
        """Initialize the flow."""
        self._issue_id = issue_id
        self._entry_id = entry_id
        self._questions: list[_Question] = []
        self._asked: set[_Question] = set()
        self._answers: dict[_Question, str] = {}
        self._add_questions(devices, entities)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Ask about the first device or entity."""
        return await self._async_next()

    async def async_step_choose_device(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Record what to keep, then ask the next question."""
        if user_input is not None:
            self._answers[self._questions.pop(0)] = user_input[CONF_KEEP]
        return await self._async_next()

    async_step_choose_earlier_device = async_step_choose_device
    async_step_choose_entity = async_step_choose_device
    async_step_choose_earlier_entity = async_step_choose_device

    def _add_questions(self, devices: list[str], entities: list[list[str]]) -> None:
        """Add the questions not asked yet, the devices before the entities."""
        for question in (
            *(("device", rest) for rest in devices),
            *(("entity", domain, rest) for domain, rest in entities),
        ):
            if question not in self._asked:
                self._asked.add(question)
                self._questions.append(question)
        self._questions.sort(key=lambda question: question[0] != "device")

    @callback
    def _async_entry(self) -> ConfigEntry | None:
        """Return the entry, if it still has the ID its identities are made from."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None or entry.unique_id is None:
            return None
        return entry

    async def _async_next(self) -> RepairsFlowResult:
        """Ask the next question that has a choice, or apply the answers.

        A loaded entry is unloaded first: the entities and devices replaced must
        not be in use, and if the unload fails nothing is changed, and the issue
        stays for after a restart. It is set up again once the answers are applied.
        """
        if (result := self._async_ask()) is not None:
            return result
        entry = self._async_entry()
        if TYPE_CHECKING:
            assert entry is not None
        if entry.state is ConfigEntryState.LOADED and self._async_changes(entry):
            try:
                unloaded = await self.hass.config_entries.async_unload(entry.entry_id)
            except OperationNotAllowed:
                return self.async_abort(reason="entry_busy")
            if not unloaded:
                return self.async_abort(reason="restart_required")
            # Set up again in any case: what changed while it unloaded is asked
            # again, with the entry loaded meanwhile.
            if (result := self._async_ask()) is None:
                self._async_apply(entry)
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            if result is not None:
                return result
        elif entry.state in (
            ConfigEntryState.SETUP_IN_PROGRESS,
            ConfigEntryState.UNLOAD_IN_PROGRESS,
        ):
            return self.async_abort(reason="entry_busy")
        elif self._async_apply(entry):
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_create_entry(data={})

    @callback
    def _async_changes(self, entry: ConfigEntry) -> bool:
        """Return whether an answer replaces a device or an entity.

        Keeping the current ones only sets the links, which needs no unload. The
        answers were checked just before: each is the current one or an earlier copy.
        """
        device_id = str(entry.unique_id)
        dev_reg = dr.async_get(self.hass)
        ent_reg = er.async_get(self.hass)
        for question, keep in self._answers.items():
            if question[0] == "device":
                current_device = dev_reg.async_get_device_by_identifier(
                    (DOMAIN, device_id + question[1]), entry.entry_id
                )
                if current_device is None or current_device.id != keep:
                    return True
                continue
            domain, rest = question[1], question[2]
            unique_id = device_id + rest
            current = _async_current_entity(ent_reg, entry, domain, unique_id)
            if current is None and ent_reg.async_get_entity_id(
                domain, DOMAIN, unique_id
            ):
                # Another entry's: not replaced.
                continue
            if current is None or current.id != keep:
                return True
        return False

    @callback
    def _async_ask(self) -> RepairsFlowResult | None:
        """Return the next question that has a choice, or None once all are answered."""
        if (entry := self._async_entry()) is None:
            return self.async_abort(reason="entry_removed")
        if entry.state is ConfigEntryState.FAILED_UNLOAD:
            # Its entities are still running, and it cannot be reloaded: the issue
            # stays, for once Home Assistant has restarted.
            return self.async_abort(reason="restart_required")
        groups = _Groups.read(self.hass, entry)
        while True:
            while self._questions:
                if form := self._async_form(entry, groups, self._questions[0]):
                    return form
                self._questions.pop(0)
            # Finishing removes the issue: questions a setup added meanwhile are
            # asked too.
            issue = ir.async_get(self.hass).async_get_issue(DOMAIN, self._issue_id)
            if issue is None:
                # Finished in another window: its answers are applied, not these.
                return self.async_abort(reason="already_finished")
            if not issue.data:
                break
            self._add_questions(*decode_ambiguous_identities(issue.data))
            if not self._questions:
                break
        # A chosen one removed meanwhile is asked again: finishing removes the
        # issue, and no setup raises it again once the entry's ID has a copy.
        for question, keep in list(self._answers.items()):
            if question[0] == "device":
                options, _, _ = self._async_device_choices(entry, groups, question[1])
            else:
                options, _, _ = self._async_entity_choices(
                    entry, groups, question[1], question[2]
                )
            if any(option["value"] == keep for option in options):
                continue
            del self._answers[question]
            if form := self._async_form(entry, groups, question):
                self._questions.insert(0, question)
                return form
        return None

    @callback
    def _async_form(
        self, entry: ConfigEntry, groups: _Groups, question: _Question
    ) -> RepairsFlowResult | None:
        """Return the form for a question, or None if there is nothing to choose.

        A sole earlier copy, with nothing under the entry's ID, is kept without
        asking.
        """
        if question[0] == "device":
            options, current, placeholders = self._async_device_choices(
                entry, groups, question[1]
            )
            step_id = "choose_device" if current else "choose_earlier_device"
        else:
            options, current, placeholders = self._async_entity_choices(
                entry, groups, question[1], question[2]
            )
            step_id = "choose_entity" if current else "choose_earlier_entity"
        if len(options) == 1 and current is None:
            self._answers[question] = options[0]["value"]
            return None
        if len(options) < 2:
            return None
        # Keeping the one set up now, the default, changes nothing.
        keep = (
            probatio.Required(CONF_KEEP, default=current)
            if current is not None
            else probatio.Required(CONF_KEEP)
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema(
                {
                    keep: SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.LIST
                        )
                    )
                }
            ),
            description_placeholders={"name": entry.title, **placeholders},
        )

    @callback
    def _async_device_choices(
        self, entry: ConfigEntry, groups: _Groups, rest: str
    ) -> tuple[list[SelectOptionDict], str | None, dict[str, str]]:
        """Return the devices to choose from, the current one, and placeholders."""
        device_id = str(entry.unique_id)
        choices = [device for device, _ in groups.devices.get(rest, [])]
        current = dr.async_get(self.hass).async_get_device_by_identifier(
            (DOMAIN, device_id + rest), entry.entry_id
        )
        if current is not None:
            choices.append(current)
        labels = _device_labels(self.hass, choices)
        return (
            [
                SelectOptionDict(value=device.id, label=labels[device.id])
                for device in choices
            ],
            current.id if current is not None else None,
            {
                "device": labels[choices[0].id] if choices else "",
                "current": labels[current.id] if current is not None else "",
            },
        )

    @callback
    def _async_entity_choices(
        self, entry: ConfigEntry, groups: _Groups, domain: str, rest: str
    ) -> tuple[list[SelectOptionDict], str | None, dict[str, str]]:
        """Return the entities to choose from, the current one, and placeholders."""
        device_id = str(entry.unique_id)
        ent_reg = er.async_get(self.hass)
        choices = list(groups.entities.get((domain, rest), []))
        current = _async_current_entity(ent_reg, entry, domain, device_id + rest)
        if current is not None:
            choices.append(current)
        # By registry ID, which a rename while the repair is open does not change.
        return (
            [
                SelectOptionDict(value=entity.id, label=_entity_label(entity))
                for entity in choices
            ],
            current.id if current is not None else None,
            {
                "entity": _entity_label(choices[0]) if choices else "",
                "current": _entity_label(current) if current is not None else "",
            },
        )

    @callback
    def _async_apply(self, entry: ConfigEntry) -> bool:
        """Apply the answers, the devices first; return whether anything changed."""
        changed = False
        groups = _Groups.read(self.hass, entry)
        # The devices that other devices are linked through, read once too.
        linked: dict[str, list[dr.DeviceEntry]] = {}
        for device in dr.async_get(self.hass).devices:
            if device.via_device_id is not None:
                linked.setdefault(device.via_device_id, []).append(device)
        for question, keep in self._answers.items():
            if question[0] == "device":
                changed |= self._async_keep_device(
                    entry, groups, linked, question[1], keep
                )
        for question, keep in self._answers.items():
            if question[0] == "entity":
                changed |= self._async_keep_entity(
                    entry, groups, question[1], question[2], keep
                )
        # Even when the current ones are kept: what the setup kept by itself may be
        # on a copy the user is now told to delete.
        async_link_to_kept_devices(self.hass, entry, str(entry.unique_id))
        return changed

    @callback
    def _async_keep_device(
        self,
        entry: ConfigEntry,
        groups: _Groups,
        linked: dict[str, list[dr.DeviceEntry]],
        rest: str,
        keep: str,
    ) -> bool:
        """Give the chosen device the identifier of the entry's ID.

        The device that has it now gives it up, and is removed if nothing else
        identifies it.
        """
        device_id = str(entry.unique_id)
        new_identifier = (DOMAIN, device_id + rest)
        dev_reg = dr.async_get(self.hass)
        current = dev_reg.async_get_device_by_identifier(new_identifier, entry.entry_id)
        if current is not None and current.id == keep:
            return False
        earlier = {
            device.id: (device, old_identifier)
            for device, old_identifier in groups.devices.get(rest, [])
        }
        device, old_identifier = earlier[keep]
        if current is not None:
            identifiers = set(current.identifiers) - {new_identifier}
            # Removing a device removes its entities and unlinks the devices linked
            # through it: if it goes, all of them move to the kept one; if it stays,
            # only what this entry has on it.
            stays = bool(identifiers or current.connections)
            ent_reg = er.async_get(self.hass)
            for entity in er.async_entries_for_device(
                ent_reg, current.id, include_disabled_entities=True
            ):
                if not stays or entity.config_entry_id == entry.entry_id:
                    ent_reg.async_update_entity(entity.entity_id, device_id=device.id)
            for cached in linked.pop(current.id, []):
                # An earlier answer can have removed it: a channel asked before its NVR.
                if (other := dev_reg.async_get(cached.id)) is not None and (
                    not stays or other.config_entry_id == entry.entry_id
                ):
                    dev_reg.async_update_device(other.id, via_device_id=device.id)
            if stays:
                dev_reg.async_update_device(current.id, new_identifiers=identifiers)
            else:
                dev_reg.async_remove_device(current.id)
        async_move_device(self.hass, device, old_identifier, new_identifier)
        return True

    @callback
    def _async_keep_entity(
        self, entry: ConfigEntry, groups: _Groups, domain: str, rest: str, keep: str
    ) -> bool:
        """Give the chosen entity, by registry ID, the unique ID of the entry's ID.

        The entity that has it now is removed. The chosen one takes its device too:
        a reload does not move an entity the camera no longer has.
        """
        device_id = str(entry.unique_id)
        new_unique_id = device_id + rest
        ent_reg = er.async_get(self.hass)
        if (
            current_id := ent_reg.async_get_entity_id(domain, DOMAIN, new_unique_id)
        ) is not None and _async_current_entity(
            ent_reg, entry, domain, new_unique_id
        ) is None:
            # Another entry's: not this camera's to replace.
            return False
        current = ent_reg.async_get(current_id) if current_id is not None else None
        if current is not None and current.id == keep:
            return False
        earlier = {
            entity.id: entity for entity in groups.entities.get((domain, rest), [])
        }
        if current is not None:
            ent_reg.async_remove(current.entity_id)
            ent_reg.async_update_entity(
                earlier[keep].entity_id,
                new_unique_id=new_unique_id,
                device_id=current.device_id,
            )
        else:
            ent_reg.async_update_entity(
                earlier[keep].entity_id, new_unique_id=new_unique_id
            )
        return True


@callback
def _async_current_entity(
    ent_reg: er.EntityRegistry, entry: ConfigEntry, domain: str, unique_id: str
) -> er.RegistryEntry | None:
    """Return the entry's entity with this unique ID, if it has one."""
    if (entity_id := ent_reg.async_get_entity_id(domain, DOMAIN, unique_id)) is None:
        return None
    entity = ent_reg.async_get(entity_id)
    if entity is None or entity.config_entry_id != entry.entry_id:
        return None
    return entity


def _entity_label(entity: er.RegistryEntry) -> str:
    """Return how an entity is shown to choose it: its name and entity ID."""
    if name := entity.name or entity.original_name:
        return f"{name} ({entity.entity_id})"
    return entity.entity_id


def _device_labels(
    hass: HomeAssistant, devices: list[dr.DeviceEntry]
) -> dict[str, str]:
    """Return how each device is shown to choose it, by device ID.

    Its name and area; copies often share both, so the start of the ID is added.
    """
    area_reg = ar.async_get(hass)
    labels: dict[str, str] = {}
    for device in devices:
        label = device.name_by_user or device.name or device.id
        if device.area_id and (area := area_reg.async_get_area(device.area_id)):
            label = f"{label} ({area.name})"
        labels[device.id] = label
    counts = Counter(labels.values())
    return {
        device_id: f"{label} [{device_id[:8]}]" if counts[label] > 1 else label
        for device_id, label in labels.items()
    }


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Create the flow that asks which earlier devices and entities to keep."""
    if not data or "entry_id" not in data:
        raise ValueError(f"Missing data for the repair of {issue_id}")
    devices, entities = decode_ambiguous_identities(data)
    return AmbiguousIdentitiesRepairFlow(issue_id, data["entry_id"], devices, entities)
