"""Resource reclamation and rescheduling for RASC."""
import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta

from homeassistant.const import (
    ANTICIPATORY,
    ATTR_ACTION_ID,
    ATTR_ENTITY_ID,
    CONF_TYPE,
    EARLIEST,
    EARLY_START,
    LATEST,
    LOCAL_FIRST,
    LOCAL_LONGEST,
    LOCAL_SHORTEST,
    LONGEST,
    PROACTIVE,
    RASC_COMPLETE,
    RASC_START,
    REACTIVE,
    RESCHEDULING_ACCURACY,
    RESCHEDULING_ESTIMATION,
    RESCHEDULING_POLICY,
    RESCHEDULING_TRIGGER,
    RESCHEDULING_WINDOW,
    ROUTINE_PRIORITY_POLICY,
    RV,
    SCHEDULING_POLICY,
    SHORTEST,
    SJFW,
    SJFWO,
    TIMELINE,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType

from .abstraction import RASC
from .const import DOMAIN, LOGGER
from .entity import ActionEntity, Queue, RoutineEntity, get_entity_id_from_number
from .scheduler import (
    BaseScheduler,
    LineageTable,
    RascalScheduler,
    datetime_to_string,
    generate_duration,
    get_routine_id,
    get_target_entities,
    string_to_datetime,
)


class BaseRescheduler(BaseScheduler):
    """Base class for rescheduling resources.

    This class is responsible for rescheduling resources based on the rescheduling policy.
    It is triggered every time an action RASC response is received.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        lineage_table: LineageTable,
        serialization_order: Queue[str, RoutineEntity],
        resched_policy: str,
        routine_priority_policy: str,
    ) -> None:
        """Initialize the background rescheduler."""
        self._hass = hass
        self._lineage_table = lineage_table
        self._serialization_order = serialization_order
        self._resched_policy = resched_policy
        self._routine_prioriy_policy = routine_priority_policy
        self._lock_leasing = "general"

    @property
    def lineage_table(self) -> LineageTable:
        """Return the lineage table."""
        return self._lineage_table

    @lineage_table.setter
    def lineage_table(self, lineage_table: LineageTable) -> None:
        """Set the lineage table."""
        self._lineage_table = lineage_table

    async def _move_device_schedule(
        self, entity_id: str, diff: float, st_time: datetime
    ) -> None:
        """Move the schedule of a device by diff seconds.

        st_time is the time in the schedule fter which actions are being moved.
        Moves locks and free slots for each device.
        """
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        last_end_before = None
        start_after = None
        diff_dt = timedelta(seconds=diff)

        # move the locks of the device by diff seconds after the start time
        for action_id, action_lock in self._lineage_table.lock_queues[
            entity_id
        ].items():
            if not action_lock:
                raise ValueError(
                    "Action {}'s schedule information on entity {} is missing.".format(
                        action_id, entity_id
                    )
                )
            if string_to_datetime(action_lock.time_range[0]) < st_time:
                # check this only if the action finished early
                if diff <= 0:
                    continue
                if (
                    not last_end_before
                    or string_to_datetime(action_lock.time_range[1]) <= last_end_before
                ):
                    continue
                last_end_before = string_to_datetime(action_lock.time_range[1])
                continue
            action_length = action_lock.action.duration or timedelta(0)
            new_action_start = string_to_datetime(action_lock.time_range[0]) + diff_dt
            if diff > 0 and not start_after:
                start_after = datetime_to_string(new_action_start)
            new_action_end = new_action_start + action_length
            new_action_slot = (
                datetime_to_string(new_action_start),
                datetime_to_string(new_action_end),
            )
            action_lock.time_range = new_action_slot

        # move the free slots of the device by diff seconds after the start time
        changed_slots = dict[str, tuple[str, str | None]]()
        for free_st_time, free_end_time in self._lineage_table.free_slots[
            entity_id
        ].items():
            if free_end_time and string_to_datetime(free_end_time) < st_time:
                continue

            if string_to_datetime(free_st_time) < st_time:
                new_st_time_dt = string_to_datetime(free_st_time)
            else:
                new_st_time_dt = string_to_datetime(free_st_time) + diff_dt

            if free_end_time:
                new_end_time_dt = string_to_datetime(free_end_time) + diff_dt
            else:
                new_end_time_dt = None
            new_slot = (
                datetime_to_string(new_st_time_dt),
                datetime_to_string(new_end_time_dt) if new_end_time_dt else None,
            )
            changed_slots[free_st_time] = new_slot

        for old_st_time, new_slot in changed_slots.items():
            self._lineage_table.free_slots[entity_id].pop(old_st_time)
            new_st_time, new_end_time = new_slot
            self._lineage_table.free_slots[entity_id][new_st_time] = (
                new_end_time if new_end_time else None
            )

        # add a free slot between the last action before the start time and the first action after the start time
        if diff > 0 and last_end_before and start_after:
            self._lineage_table.free_slots[entity_id][start_after] = datetime_to_string(
                last_end_before
            )

    async def move_device_schedules(
        self, diff: float, st_time: datetime
    ) -> LineageTable:
        """Move the schedules of all devices according to diff (seconds)."""
        tasks = []
        for entity_id in self._lineage_table.lock_queues:
            tasks.append(
                asyncio.create_task(
                    self._move_device_schedule(entity_id, diff, st_time)
                )
            )
        for task in tasks:
            await task
        return self._lineage_table

    async def RV(self) -> LineageTable:
        """Reschedule actions using the RV resource reclamation algorithm."""
        return self._lineage_table

    async def early_start(self) -> LineageTable:
        """Reschedule actions using the Early Start resource reclamation algorithm."""
        return self._lineage_table

    async def affected_src_actions_after_len_diff(
        self, entity_id: str, action_id: str, time: datetime
    ) -> set[ActionEntity]:
        """Find source actions of routines or independent actions affected by overtime.

        These actions are not running right now, they are scheduled into the future.
        """
        affected_actions: set[ActionEntity] = set[ActionEntity]()

        # the same action's children are affected
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in self._lineage_table.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action_lock = self._lineage_table.lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )
        action = action_lock.action
        affected_actions.update(action.children)

        # the next action in the same entity's schedule is affected
        next_action_lock = self._lineage_table.lock_queues[entity_id].next(action_id)
        if next_action_lock:
            next_action = next_action_lock.action
            affected_actions.add(next_action)

        # the actions in routines serialized after this action's routine are affected
        if not action.routine_id:
            return affected_actions
        routines_after = self._routines_serialized_after(action.routine_id)
        for routine_id in routines_after:
            affected_actions |= self._current_routine_source_actions(routine_id, time)

        return affected_actions

    def _routine_ranks(
        self,
        routine_ids: set[str] | None = None,
        routines: set[RoutineEntity] | None = None,
    ) -> dict[str, float]:
        """Rank the routines based on the routine priority policy."""
        routine_ranks = dict[str, float]()
        if not routine_ids and not routines:
            return routine_ranks
        if not routines:
            routines = set[RoutineEntity](
                [
                    routine
                    for routine_id, routine in self._serialization_order.items()
                    if routine_ids and routine_id in routine_ids and routine
                ]
            )

        for routine in routines:
            routine_id = routine.routine_id
            if not routine_id:
                continue
            if self._routine_prioriy_policy in (EARLIEST, LATEST):
                routine_ranks[routine_id] = routine.start_time or 0.0
                continue
            if self._routine_prioriy_policy in (SHORTEST, LONGEST):
                # can change this in the future
                routine_ranks[routine_id] = float(len(routine.actions))
                continue
            routine_ranks[routine_id] = 0.0
        return routine_ranks

    def immutable_serialization_order(self, now: datetime) -> list[str]:
        """Return the now-immutable serialization order."""
        immutable_order = list[str]()
        postsets = dict[str, set[str]]()
        for routine_id in self._serialization_order:
            # presets[routine_id] = set[str]()
            postsets[routine_id] = set[str]()
            for entity_id, lock_queue in self._lineage_table.lock_queues.items():
                found = False
                for action_id, action_lock in lock_queue.items():
                    if not action_lock:
                        raise ValueError(
                            "Action {}'s schedule information on entity {} is missing.".format(
                                action_id, entity_id
                            )
                        )
                    time_range = action_lock.time_range
                    if string_to_datetime(time_range[0]) > now:
                        break
                    action = action_lock.action
                    if not action.routine_id:
                        continue

                    if not found and action.routine_id == routine_id:
                        found = True
                        continue
                    if found and action.routine_id not in postsets[routine_id]:
                        postsets[routine_id] |= {action.routine_id}

        while postsets:
            before = set[str]()
            for routine_id, postset in postsets.items():
                if not postset:
                    before.add(routine_id)
                    break
            if not before:
                raise ValueError("There is a cycle in the serialization order.")

            for routine_id in before:
                postsets.pop(routine_id)
                for routine_id, postset in postsets.items():
                    postset.discard(routine_id)

            routine_ranks: dict[str, float] = self._routine_ranks(routine_ids=before)
            if self._routine_prioriy_policy in (EARLIEST, SHORTEST):
                routine_order = dict(sorted(routine_ranks.items(), key=lambda x: x[1]))
            elif self._routine_prioriy_policy in (LATEST, LONGEST):
                routine_order = dict(
                    sorted(routine_ranks.items(), key=lambda x: x[1], reverse=True)
                )
            else:
                routine_order = routine_ranks
            immutable_order = list(routine_order.keys()) + immutable_order

        return immutable_order

    async def deschedule_affected_and_later_actions(
        self, affected_source_actions: set[ActionEntity]
    ) -> tuple[set[str], set[ActionEntity], set[str]]:
        """Deschedule the affected actions and the actions after them on each entity.

        Returns:
            set[str]: The descheduled source action IDs (includes current routine
            source actions and independent actions).
            set[ActionEntity]: All the descheduled actions.
            set[str]: The affected entities.
        """
        descheduled_source_action_ids = {
            action.action_id for action in affected_source_actions if action.action_id
        }
        descheduled_actions = set[ActionEntity]()
        affected_entities = set[str]()
        for entity_id, lock_queue in self._lineage_table.lock_queues.items():
            free_st_time = None
            to_remove = []

            # identify all actions to be descheduled from the lock queue
            for action_id, action_lock in lock_queue.items():
                if not action_lock:
                    raise ValueError(
                        "Action {}'s schedule information on entity {} is missing.".format(
                            action_id, entity_id
                        )
                    )
                if not free_st_time:
                    # while a source action is not found, skip the action
                    if action_lock.action not in affected_source_actions:
                        continue
                    # record the first action's start time
                    # to create a free slot later
                    free_st_time = action_lock.time_range[0]
                # after a source action has been found while traversing in ascending
                # chronological order, add every action to the descheduled actions
                # (including the found source action)
                to_remove.append(action_id)
                affected_entities.add(entity_id)

            # remove the actions from the lock queue
            for action_id in to_remove:
                descheduled_action_lock = lock_queue.pop(action_id)
                if descheduled_action_lock:
                    descheduled_action = descheduled_action_lock.action
                    descheduled_actions.add(descheduled_action)

            # create one big free slot replacing the descheduled actions
            if free_st_time:
                free_slots = self._lineage_table.free_slots[entity_id]
                for st_time, end_time in free_slots.items():
                    if end_time and end_time >= free_st_time:
                        free_slots.pop(st_time)
                free_slots[free_st_time] = None

        return descheduled_source_action_ids, descheduled_actions, affected_entities

    async def apply_serialization_order_dependencies(
        self, immutable_order: list[str], descheduled_actions: set[ActionEntity]
    ) -> set[ActionEntity]:
        """Apply the existing serialization order as routine action dependencies."""
        entity_descheduled_actions = dict[str, dict[str, list[ActionEntity]]]()
        for routine_id in immutable_order:
            routine_bfs = self._routine_actions_bfs(routine_id)
            for action in routine_bfs:
                if action not in descheduled_actions:
                    continue
                target_entities = get_target_entities(self._hass, action.action)
                for entity_id in target_entities:
                    if entity_id not in entity_descheduled_actions:
                        entity_descheduled_actions[entity_id] = dict[
                            str, list[ActionEntity]
                        ]()
                    if routine_id not in entity_descheduled_actions[entity_id]:
                        entity_descheduled_actions[entity_id][routine_id] = []
                    entity_descheduled_actions[entity_id][routine_id].append(action)

        actions_with_dependencies = set[ActionEntity]()
        for routine_actions in entity_descheduled_actions.values():
            prev_routine_id = None
            for routine_id, actions in routine_actions.items():
                if not actions:
                    continue
                if not prev_routine_id:
                    prev_routine_id = routine_id
                    continue
                # add dependencies to all the actions
                # of the previous routine on the same entity
                # this way, each action in a routine
                # may have dependencies to multiple different routines
                for action in actions:
                    for pre_action in routine_actions[prev_routine_id]:
                        pre_action.children.append(action)
                        action.parents.append(pre_action)

                for action in actions:
                    actions_with_dependencies.add(action)
                prev_routine_id = routine_id
        return actions_with_dependencies

    def _add_new_routine_serialization_dependencies(
        self,
        remaining_descheduled_actions: set[ActionEntity],
        old_serialization_order: Queue[str, RoutineEntity],
        new_routine_id: str,
    ) -> set[ActionEntity]:
        # find all remaining descheduled actions from routines serialized before
        # the new routine and assign routine serialization dependencies accordingly
        actions_per_entity = dict[str, set[ActionEntity]]()
        for action in remaining_descheduled_actions:
            if not action.routine_id:
                continue
            if action.routine_id not in old_serialization_order:
                continue
            target_entities = get_target_entities(self._hass, action.action)
            for entity_id in target_entities:
                if entity_id not in actions_per_entity:
                    actions_per_entity[entity_id] = set[ActionEntity]()
                actions_per_entity[entity_id].add(action)

        for action in remaining_descheduled_actions:
            if not action.routine_id:
                continue
            if action.routine_id != new_routine_id:
                continue
            # add dependencies to the earlier serialized routines' actions
            # on the same entity to maintain the serializability order
            target_entities = get_target_entities(self._hass, action.action)
            for entity_id in target_entities:
                if entity_id not in actions_per_entity:
                    continue
                action.parents += list(actions_per_entity[entity_id])
                for parent in actions_per_entity[entity_id]:
                    parent.children.append(action)

        return remaining_descheduled_actions

    async def sjf(  # noqa: C901
        self,
        st_time: datetime,
        descheduled_source_action_ids: set[str],
        descheduled_actions: set[ActionEntity],
        entities: set[str],
        immutable_serialization_order: list[str],
        serializability_guarantee: bool,
        # window: timedelta
    ) -> LineageTable:
        """Shortest Job First rescheduling w/ and w/o routine serializability guarantee.

        Initially, initialize the serialization order,
        and next slots and wait queues for each entity.

        Then, put all the source descheduled actions into the wait queues.
        If the serializability guarantee is desired, make sure that actions put into the
        wait queues do not have dependencies to unscheduled actions from the routines
        serialized before. This check has not been done earlier.

        While there are still descheduled actions:
        - Filter out entities with no actions to schedule.
        - Find the entity with the earliest next slot.
        - Find the action with the shortest duration.
        - Schedule the action on all entities it affects.
        - Update the next slot for each target entity and remove the action from the wait
          queues.
        - Remove the chosen action from the descheduled actions.
        - If the serializability guarantee is desired and this was the first action of
          a routine to be scheduled, add it to the end of the serialization order,
          and add dependencies from its remaining descheduled actions to the earlier
          serialized routines' remainng descheduled actions meant to execute on the same
          entity to maintain the serializability order.
        - Add children of the chosen action to the affected entities' wait queues. Add
          only the children whose parents (same or other routine) are all scheduled.
        - Reinitialize the children's affected entities' wait queue and next slot if
          needed.

        Return the updated lineage table.
        """
        # initialize the new serialization order, if desired
        if serializability_guarantee:
            old_serialization_order = self._serialization_order
            self._serialization_order.clear()
            for routine_id in immutable_serialization_order:
                self._serialization_order[routine_id] = old_serialization_order[
                    routine_id
                ]

        # initialize the next slots and wait queues for each entity
        next_slots = dict[str, str]()
        wait_queues = dict[str, set[ActionEntity]]()
        for entity_id in entities:
            last_slot_start = self._lineage_table.free_slots[entity_id].end()[0]
            if not last_slot_start:
                continue
            next_slots[entity_id] = last_slot_start
            wait_queues[entity_id] = set[ActionEntity]()

        for action in descheduled_actions:
            # skip the action if it is not a source action
            if (
                action.action_id
                or action.action_id not in descheduled_source_action_ids
            ):
                continue

            # this is required to guarantee serializability if desired
            # in this case, serialization order dependencies
            # have been added to the descheduled actions
            # while calling self.apply_serialization_order_dependencies()
            # and these actions will be added to the wait queues later
            if serializability_guarantee:
                for parent in action.parents:
                    if parent.routine_id != action.routine_id:
                        continue

            target_entities = get_target_entities(self._hass, action.action)
            for entity_id in target_entities:
                if entity_id not in wait_queues:
                    wait_queues[entity_id] = set[ActionEntity]()
                if entity_id not in next_slots:
                    last_slot_start = self._lineage_table.free_slots[entity_id].end()[0]
                    if not last_slot_start:
                        continue
                    next_slots[entity_id] = last_slot_start

                wait_queues[entity_id].add(action)

        while descheduled_actions:
            # filter out entities with no actions to schedule
            filtered_next_slots = {
                k: v for k, v in next_slots.items() if wait_queues[k]
            }
            # find the entity with the earliest next slot
            # can generalize for any metric to be used here
            next_entity_id, next_slot_st = min(
                filtered_next_slots.items(), key=lambda x: string_to_datetime(x[1])
            )

            # find the action with the shortest duration
            shortest_action = None
            for action in wait_queues[next_entity_id]:
                if not action.duration:
                    action.duration = timedelta(0)
                if not shortest_action or action.duration < shortest_action.duration:
                    shortest_action = action
                if not shortest_action.duration:
                    shortest_action.duration = timedelta(0)

            if not shortest_action:
                wait_queues.pop(next_entity_id)
                next_slots.pop(next_entity_id)
                continue
            if not shortest_action.duration:
                shortest_action.duration = timedelta(0)

            # schedule the action on all entities it affects
            target_entities = get_target_entities(self._hass, shortest_action.action)
            next_slot_st_dt = string_to_datetime(next_slot_st)
            action_slot = await self._identify_first_common_idle_time_after(
                target_entities, next_slot_st_dt, shortest_action.duration
            )
            action_st_dt = string_to_datetime(action_slot[0])
            # TODO: requires more careful handling regarding lock leasing, ask Ting/study tl code # pylint: disable=fixme
            self.schedule_all_action(
                shortest_action,
                action_st_dt,
                self._lineage_table.free_slots,
                self._lock_leasing,
            )

            # update the next slot for each target entity
            # and remove the action from the wait queues
            to_remove = set[str]()
            for entity_id in target_entities:
                wait_queues[entity_id].remove(shortest_action)
                if not wait_queues[entity_id]:
                    to_remove.add(entity_id)
                    continue
                next_slots[entity_id] = datetime_to_string(
                    action_st_dt + shortest_action.duration
                )

            # remove the chosen action from the descheduled actions
            descheduled_actions.remove(shortest_action)

            if serializability_guarantee:
                shortest_action_routine_id = shortest_action.routine_id
                if (
                    shortest_action_routine_id
                    and shortest_action_routine_id not in self._serialization_order
                ):
                    descheduled_actions = (
                        self._add_new_routine_serialization_dependencies(
                            descheduled_actions,
                            old_serialization_order,
                            shortest_action_routine_id,
                        )
                    )
                    self._serialization_order[
                        shortest_action_routine_id
                    ] = old_serialization_order[shortest_action_routine_id]

            # add children of the chosen action to the affected entities' wait queues
            for child in shortest_action.children:
                # eligible children are those whose parents are all scheduled

                for parent in child.parents:
                    target_entities = get_target_entities(self._hass, parent.action)
                    if any(
                        parent not in self._lineage_table.lock_queues[parent_entity_id]
                        for parent_entity_id in target_entities
                    ):
                        break
                else:
                    continue

                # reinitialize the affected entities' wait queue and next slot if need be
                target_entities = get_target_entities(self._hass, child.action)
                for entity_id in target_entities:
                    if entity_id in to_remove:
                        to_remove.remove(entity_id)

                    if entity_id not in wait_queues:
                        wait_queues[entity_id] = set[ActionEntity]()
                    wait_queues[entity_id].add(child)

                    if entity_id not in next_slots:
                        last_slot_start = self._lineage_table.free_slots[
                            entity_id
                        ].end()[0]
                        if not last_slot_start:
                            continue
                        next_slots[entity_id] = last_slot_start

            for entity_id in to_remove:
                wait_queues.pop(entity_id)
                next_slots.pop(entity_id)

        return self._lineage_table

    async def optimal(
        self,
        st_time: datetime,
        descheduled_source_action_ids: set[str],
        descheduled_actions: set[ActionEntity],
        entities: set[str],
        immutable_serialization_order: list[str],
        serializability_guarantee: bool,
        # window: timedelta
    ) -> LineageTable:
        """Optimal rescheduling with routine serializability guarantee."""

        return self._lineage_table

    async def _identify_first_common_idle_time_after(
        self, entities: list[str], time: datetime, length: timedelta
    ) -> tuple[str, str | None]:
        """Find the idle time across the supplied entities.

        Returns:
            tuple[str, str]: The start and end times of the time range. If no common idle
              time is found, return None, None.
        """

        def _common_idle_time(
            first: tuple[str, str | None], second: tuple[str, str | None]
        ) -> tuple[str, str | None] | tuple[None, None]:
            start_time = max(first[0], second[0])
            first_end = first[1]
            second_end = second[1]
            if not first_end and not second_end:
                return start_time, None
            if not first_end and second_end:
                end_time = second_end
            elif first_end and not second_end:
                end_time = first_end
            elif not first_end or not second_end:
                raise ValueError("Not possible scenario.")
            else:
                end_time = min(first_end, second_end)
            if start_time <= end_time:
                return start_time, end_time
            return None, None

        if not self._lineage_table.free_slots:
            raise ValueError("The lineage table's free slots are empty.")

        found = False
        common_idle_end = None
        starting_entity_id: str = entities[0]
        while not found:
            time_str = datetime_to_string(time)
            for time_range in self._lineage_table.free_slots[
                starting_entity_id
            ].items():
                possible_common_idle_time = _common_idle_time(
                    time_range, (time_str, None)
                )
                possible_common_st, possible_common_end = possible_common_idle_time
                if not possible_common_st:
                    continue
                common_idle_st, common_idle_end = (
                    possible_common_st,
                    possible_common_end,
                )
                time = max(time, string_to_datetime(common_idle_st))
                break
            if not possible_common_st:
                raise ValueError(
                    "No common idle time found for entity {} with ({}, None).".format(
                        starting_entity_id, time.strftime("%Y-%m-%d %H:%M:%S")
                    )
                )

            for entity_id, free_slots in self._lineage_table.free_slots.items():
                if entity_id == starting_entity_id or entity_id not in entities:
                    continue

                found = False
                for time_range in free_slots.items():
                    if time_range[1] and string_to_datetime(time_range[1]) < time:
                        continue

                    possible_common_st, possible_common_end = _common_idle_time(
                        time_range, (common_idle_st, common_idle_end)
                    )
                    if not possible_common_st:
                        time = max(time, string_to_datetime(time_range[0]))
                        continue

                    if possible_common_end:
                        possible_common_st_dt = string_to_datetime(possible_common_st)
                        possible_common_end_dt = string_to_datetime(possible_common_end)
                        if possible_common_end_dt - possible_common_st_dt < length:
                            time = max(time, possible_common_st_dt + length)
                            continue
                    common_idle_st, common_idle_end = (
                        possible_common_st,
                        possible_common_end,
                    )
                    time = max(time, string_to_datetime(possible_common_st))
                    found = True
                    break
                if not found:
                    break

        if not common_idle_st:
            raise ValueError("No common idle time found among all entities.")
        return common_idle_st, common_idle_end

    async def _identify_first_universal_common_idle_time_after(
        self, time: datetime, length: timedelta
    ) -> tuple[str | None, str | None]:
        """Find the idle time across entities.

        Returns:
            tuple[str, str]: The start and end times of the time range. If no common idle
              time is found, return None, None.
        """

        return await self._identify_first_common_idle_time_after(
            list(self._lineage_table.free_slots.keys()), time, length
        )

    async def _find_slot_for_action_after(
        self, entity_id: str, action_id: str, time: datetime
    ) -> tuple[str | None, str | None, str | None]:
        """Find a slot for the action after the specified time."""
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in self._lineage_table.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action_lock = self._lineage_table.lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )

        action_length = action_lock.action.duration or timedelta(0)
        for st_time, end_time in self._lineage_table.free_slots[entity_id].items():
            if end_time and string_to_datetime(end_time) <= time:
                continue
            new_st_time = max(time, string_to_datetime(st_time))
            new_end_time = new_st_time + action_length
            if not end_time or new_end_time <= string_to_datetime(end_time):
                return (st_time, end_time, datetime_to_string(new_st_time))
        return None, None, None

    def _next_independent_actions_before(
        self, action: ActionEntity, new_end_time: datetime
    ) -> set[ActionEntity]:
        """Find the next actions in the lineage table."""
        if not action.action_id:
            return set[ActionEntity]()
        target_entities = get_target_entities(self._hass, action.action)
        next_actions = set[ActionEntity]()
        for entity_id in target_entities:
            lock_queue = self._lineage_table.lock_queues[entity_id]
            next_action_lock = lock_queue.next(action.action_id)
            if not next_action_lock:
                continue
            next_action = next_action_lock.action
            while string_to_datetime(next_action_lock.time_range[0]) < new_end_time:
                next_actions.add(next_action)
                next_action_lock = lock_queue.next(next_action.action_id)
                if not next_action_lock:
                    break
                next_action = next_action_lock.action
        return next_actions

    def _routines_serialized_after(self, routine_id: str) -> set[str]:
        """Find the routines that are serialized after the specified routine."""
        routines_after = set[str]()
        found = False
        for other_routine_id in self._serialization_order:
            if not found and other_routine_id == routine_id:
                found = True
                continue
            if found:
                routines_after |= {other_routine_id}
        return routines_after

    def _bfs_actions(self, actions: list[ActionEntity]) -> list[ActionEntity]:
        """Perform breadth-first search on the action dependencies."""
        bfs_actions = actions
        index = 0
        while index < len(bfs_actions):
            action = bfs_actions[index]
            for child in action.children:
                if child not in bfs_actions:
                    bfs_actions.append(child)
            index += 1
        return bfs_actions

    def _routine_source_actions(self, routine_id: str) -> list[ActionEntity]:
        routine = self._serialization_order[routine_id]
        if not routine:
            raise ValueError("Routine %s has not been scheduled." % routine_id)
        sources = []
        for action in routine.actions.values():
            if not action.parents:
                sources.append(action)
        return sources

    def _routine_actions_bfs(self, routine_id: str) -> list[ActionEntity]:
        """Perform breadth-first search on the actions of the routine."""
        sources = self._routine_source_actions(routine_id)
        return self._bfs_actions(sources)

    def _dependent_actions(self, entity_id: str, action_id: str) -> list[ActionEntity]:
        """Find the actions that are dependent on the specified action."""
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in self._lineage_table.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action_lock = self._lineage_table.lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )
        action = action_lock.action
        # remove the action itself from the bfs result
        return self._bfs_actions([action])[1:]

    def _current_routine_source_actions(
        self, routine_id: str, time: datetime
    ) -> set[ActionEntity]:
        next_batch = set(self._routine_source_actions(routine_id))
        current_sources = set[ActionEntity]()
        visited = set[ActionEntity]()

        while next_batch:
            candidates = next_batch
            next_batch = set[ActionEntity]()
            for action in candidates:
                visited.add(action)
                if action.routine_id != routine_id:
                    continue
                action_id = action.action_id
                if not action_id:
                    continue
                target_entities = get_target_entities(self._hass, action.action)
                scheduled = True
                for entity_id in target_entities:
                    if entity_id not in self._lineage_table.lock_queues:
                        raise ValueError("Entity %s has no schedule." % entity_id)
                    if action_id not in self._lineage_table.lock_queues[entity_id]:
                        raise ValueError(
                            "Action {} has not been scheduled on entity {}.".format(
                                action_id, entity_id
                            )
                        )
                    action_lock = self._lineage_table.lock_queues[entity_id][action_id]
                    if not action_lock:
                        raise ValueError(
                            "Action {}'s schedule information on entity {} is missing.".format(
                                action_id, entity_id
                            )
                        )
                    if string_to_datetime(action_lock.time_range[0]) < time:
                        scheduled = False
                        break
                # if the action is scheduled to run after the specified time,
                # add it to the current sources and don't check any children
                if scheduled:
                    current_sources.add(action)
                    continue
                # only when all parents of a child have been visited,
                # add it to the next batch
                for child in action.children:
                    if all(parent in visited for parent in child.parents):
                        next_batch.add(child)
        return current_sources

    def _routine_actions_on_entity_from_bfs(
        self, routine_id: str, entity_id: str
    ) -> list[ActionEntity]:
        """Find the actions on the entity from the bfs result."""
        routine_actions = self._routine_actions_bfs(routine_id)
        return [
            action
            for action in routine_actions
            if entity_id in get_target_entities(self._hass, action.action)
        ]

    def _find_actions_breaking_routine_order(
        self, dependent_actions: list[ActionEntity], time: datetime
    ) -> dict[str, set[ActionEntity]]:
        """Find the actions that must be displaced after the specified action.

        If not displaced, they break the serializability order.
        Affected actions are actions on the same entities as the children actions
        from routines that are serialized after this action's routine, if any.

        Return only the current source-actions of each routine that must be displaced.
        """
        # if the action is independent from a routine, this is the only action to displace
        action = dependent_actions[0]
        if not action.routine_id:
            return dict[str, set[ActionEntity]]()
        action_routine = self._serialization_order[action.routine_id]
        if not action_routine:
            return dict[str, set[ActionEntity]]()

        # find the routines that are serialized after the initial routine
        routines_after = self._routines_serialized_after(action.routine_id)

        # find the actions from the routines serialized after this action's routine
        # that must be displaced to maintain the existing serializability order
        routine_actions_to_displace = dict[str, set[ActionEntity]]()
        for routine_id in routines_after:
            routine_actions_to_displace[
                routine_id
            ] = self._current_routine_source_actions(routine_id, time)

        return routine_actions_to_displace

    def _max_parent_end_time(self, action: ActionEntity, now: datetime) -> datetime:
        """Find the maximum end time of the parent actions."""
        max_parent_end_time = now
        for parent_action in action.parents:
            parent_action_id = parent_action.action_id
            if not parent_action_id:
                raise ValueError("The parent action does not have an action ID.")
            target_entities = get_target_entities(self._hass, parent_action.action)
            for entity_id in target_entities:
                action_lock = self._lineage_table.lock_queues[entity_id][
                    parent_action_id
                ]
                if not action_lock:
                    raise ValueError(
                        "Action {}'s schedule information on entity {} is missing.".format(
                            parent_action_id, entity_id
                        )
                    )
                if not max_parent_end_time:
                    max_parent_end_time = string_to_datetime(action_lock.time_range[1])
                    continue
                max_parent_end_time = max(
                    max_parent_end_time,
                    string_to_datetime(action_lock.time_range[1]),
                )
        return max_parent_end_time

    def _action_start_time(self, action: ActionEntity) -> datetime:
        """Find the start time of the action on the current schedule."""
        if not action.action_id:
            raise ValueError("The action does not have an action ID.")
        target_entities = get_target_entities(self._hass, action.action)
        if not target_entities:
            raise ValueError(
                "Action %s does not have any target entities." % action.action_id
            )
        earliest_action_start = None
        for entity_id in target_entities:
            if entity_id not in self._lineage_table.lock_queues:
                raise ValueError("Entity %s has no schedule." % entity_id)
            if action.action_id not in self._lineage_table.lock_queues[entity_id]:
                raise ValueError(
                    "Action {} has not been scheduled on entity {}.".format(
                        action.action_id, entity_id
                    )
                )
            action_lock = self._lineage_table.lock_queues[entity_id][action.action_id]
            if not action_lock:
                raise ValueError(
                    "Action {}'s schedule information on entity {} is missing.".format(
                        action.action_id, entity_id
                    )
                )
            if not earliest_action_start:
                earliest_action_start = string_to_datetime(action_lock.time_range[0])
                continue
            earliest_action_start = min(
                earliest_action_start, string_to_datetime(action_lock.time_range[0])
            )
        if not earliest_action_start:
            raise ValueError("Action %s has not been scheduled." % action.action_id)
        return earliest_action_start

    def _action_length_on_entity(self, entity_id: str, action_id: str) -> timedelta:
        """Find the duration of the action on the entity."""
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in self._lineage_table.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action_lock = self._lineage_table.lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )
        action_length = action_lock.action.duration
        return action_length or timedelta(0)

    def _return_free_slot(self, entity_id: str, action_id: str) -> bool:
        """Return the slot of the action to the free slots."""
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in self._lineage_table.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action_lock = self._lineage_table.lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )
        old_action_start, old_action_end = action_lock.time_range
        key = old_action_start
        entity_free_slots = self._lineage_table.free_slots[entity_id]
        for slot_start, slot_end in entity_free_slots.items():
            if slot_end == old_action_start:
                key = slot_start
                break
        entity_free_slots[key] = old_action_end
        if old_action_end in entity_free_slots:
            new_val = entity_free_slots[old_action_end]
            entity_free_slots[key] = new_val
            entity_free_slots.pop(old_action_end)
        return True

    def _remove_routine_from_serialization_order(self, routine_id: str) -> None:
        """Remove routine from the serialization order."""
        LOGGER.info("Remove routine %s from the serialization order", routine_id)
        self._serialization_order.pop(routine_id)

    def _remove_routine_from_lock_queues(self, routine: RoutineEntity) -> None:
        """Remove routine from lock queues."""
        for action in list(routine.actions.values())[:-1]:
            target_entities = get_target_entities(self._hass, action.action)
            for entity in target_entities:
                entity_id = get_entity_id_from_number(self._hass, entity)
                if action.action_id is not None:
                    self._lineage_table.lock_queues[entity_id].pop(action.action_id)

    def _release_routine_locks(self, routine: RoutineEntity) -> None:
        """Release all the locks for the routine."""
        LOGGER.info("Release all locks for the routine %s", routine.routine_id)

        for action in list(routine.actions.values())[:-1]:
            self._release_all_locks(action)

    def _release_all_locks(self, action: ActionEntity) -> None:
        """Release all locks for the action."""
        target_entities = get_target_entities(self._hass, action.action)
        for entity in target_entities:
            entity_id = get_entity_id_from_number(self._hass, entity)
            if not action.action_id:
                return
            if self._lineage_table.locks[entity_id] == get_routine_id(action.action_id):
                self._release_lock(entity_id)

    def _release_lock(self, entity_id: str) -> None:
        """Release the lock for the entity."""
        LOGGER.info("Release the lock %s", entity_id)
        self._lineage_table.locks[entity_id] = None

    async def displace_action_to_idle_time(  # noqa: C901
        self, entity_id: str, action_id: str, new_end_time: datetime, lock_leasing: str
    ) -> LineageTable | None:
        """Displace an action to the idle time.

        This action's displacement may lead to the displacement of other actions.
        Affected actions are:
        1. children actions in the same routine, and
        2. actions from routines that are serialized after this action's routine, if any.

        First, we identiify the actions that must be displaced based on these criteria.
        Second, we deschedule the identified actions. If an action is a group action,
        we deschedule it from all affected entities.
        (TODO: Should we move up the remaining actions with early start at this point?
        Or should the second and third step not be decoupled?
        Disregarding these questions right now for a simpler implementation.)
        Third, we find the idle time after the specified time and displace the actions.

        Finally, we examine and repair lock relationships between displaced actions and
        others on the affected entities.
        """

        # get the current source actions of the routine serialized after this action's routine
        dependent_actions = self._dependent_actions(entity_id, action_id)
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in self._lineage_table.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action_lock = self._lineage_table.lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )
        action = action_lock.action
        next_independent_actions = self._next_independent_actions_before(
            action, new_end_time
        )
        routines_after_actions: dict[
            str, set[ActionEntity]
        ] = self._find_actions_breaking_routine_order(dependent_actions, new_end_time)

        # coupled second and third steps
        # reschedule the following/dependent actions in the same routine
        for action in dependent_actions:
            if not action.action_id:
                raise ValueError(
                    f"A dependent action of action {action_id} does not have an action ID."
                )
            # check if parent actions are still in the queue before the action to be rescheduled.
            # if so, continue. otherwise, reschedule the action.
            max_parent_end_time = self._max_parent_end_time(action, new_end_time)
            action_start_time = self._action_start_time(action)
            if max_parent_end_time <= action_start_time:
                continue
            target_entities = get_target_entities(self._hass, action.action)
            action_length = action.duration or timedelta(0)
            (
                new_slot_st,
                _,
            ) = await self._identify_first_common_idle_time_after(
                target_entities, max_parent_end_time, action_length
            )
            tasks = []
            for entity in target_entities:
                tasks.append(
                    asyncio.create_task(
                        self._fill_slot(entity, action.action_id, new_slot_st)
                    )
                )
            for task in tasks:
                await task

        # reschedule the following actions from the routines serialized after this action's routine
        # reschedule per routine, in ascending serialization order
        # if a routine needs to be rescheduled completely, deschedule it and call schedule_routine
        # else, call self._find_slot_for_action_after() and self._fill_slot()
        end_time_per_entity = dict[str, datetime]()
        whole_routines_to_reschedule = dict[str, RoutineEntity]()
        for routine_id, source_actions in routines_after_actions.items():
            current_routine_action_set = self._bfs_actions(list(source_actions))
            complete_routine_action_set = self._routine_actions_bfs(routine_id)
            if set(current_routine_action_set) != set(complete_routine_action_set):
                for action in current_routine_action_set:
                    if not action.action_id:
                        raise ValueError(
                            f"An action in routine {routine_id} does not have an action ID."
                        )
                    target_entities = get_target_entities(self._hass, action.action)
                    # max end time of the parent actions from the same routine
                    max_parent_end_time = self._max_parent_end_time(
                        action, new_end_time
                    )
                    # max end time of the actions from routines serialized before this routine
                    max_routine_end_time = new_end_time
                    for target_entity_id in target_entities:
                        if (
                            not max_routine_end_time
                            or end_time_per_entity[target_entity_id]
                            > max_routine_end_time
                        ):
                            max_routine_end_time = end_time_per_entity[target_entity_id]
                    max_end_time = max(max_parent_end_time, max_routine_end_time)
                    action_length = action.duration or timedelta(0)
                    (
                        new_slot_st,
                        _,
                    ) = await self._identify_first_common_idle_time_after(
                        target_entities, max_end_time, action_length
                    )
                    for target_entity_id in target_entities:
                        await self._fill_slot(
                            target_entity_id,
                            action.action_id,
                            new_slot_st,
                        )
                        new_slot_st_dt = string_to_datetime(new_slot_st)
                        action_lock = self._lineage_table.lock_queues[target_entity_id][
                            action.action_id
                        ]
                        if not action_lock:
                            raise ValueError(
                                "Action {}'s schedule information on entity {} is missing.".format(
                                    action.action_id, target_entity_id
                                )
                            )
                        action_length = action_lock.action.duration or timedelta(0)
                        action_end_dt = new_slot_st_dt + action_length
                        end_time_per_entity[target_entity_id] = max(
                            end_time_per_entity.get(target_entity_id, action_end_dt),
                            action_end_dt,
                        )
                continue
            # if the routine has not started execution, deschedule the routine completely
            # and reschedule it when all the already running routines are rescheduled
            routine = self._serialization_order[routine_id]
            if not routine:
                raise ValueError("Routine %s has not been scheduled." % routine_id)

            whole_routines_to_reschedule[routine_id] = routine
            self._remove_routine_from_lock_queues(routine)
            self._remove_routine_from_serialization_order(routine_id)

        # reschedule the unstarted routines from scratch
        routines = set(whole_routines_to_reschedule.values())
        routine_ranks: dict[str, float] = self._routine_ranks(routines=routines)
        if self._routine_prioriy_policy in (EARLIEST, SHORTEST):
            routine_order = dict(sorted(routine_ranks.items(), key=lambda x: x[1]))
        elif self._routine_prioriy_policy in (LATEST, LONGEST):
            routine_order = dict(
                sorted(routine_ranks.items(), key=lambda x: x[1], reverse=True)
            )
        elif routine_ranks:
            routine_order = routine_ranks
        else:
            routine_order = {
                routine_id: 0.0 for routine_id in whole_routines_to_reschedule
            }

        for routine_id in routine_order:
            if routine_id not in whole_routines_to_reschedule:
                continue
            routine = whole_routines_to_reschedule.pop(routine_id)
            self.schedule_routine(self._hass, routine, self._lock_leasing)

        for action in next_independent_actions:
            if not action.action_id:
                raise ValueError("An independent action does not have an action ID.")
            target_entities = get_target_entities(self._hass, action.action)
            action_length = action.duration or timedelta(0)
            (
                new_slot_st,
                _,
            ) = await self._identify_first_common_idle_time_after(
                target_entities, new_end_time, action_length
            )
            tasks = []
            for entity in target_entities:
                tasks.append(
                    asyncio.create_task(
                        self._fill_slot(entity, action.action_id, new_slot_st)
                    )
                )
            for task in tasks:
                await task

        return self._lineage_table

    def _eligibility_test(  # noqa: C901
        self, entity_id: str, action_id: str, time_range: tuple[str, str | None]
    ) -> str | None:
        """Check if the action can move into the time range.

        There are several requirements:
        1. Group-action single-entity action move not allowed.
        2. The action can finish before the slot end.
        3. The latest parent action end time is before the action start time.
           No need to check older ascendants.
        4. Routine serializability order is not violated.
        """
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        entity_lock_queue = self._lineage_table.lock_queues[entity_id]
        if action_id not in entity_lock_queue:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action_lock = entity_lock_queue[action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )
        action = action_lock.action

        # group-action single-entity action check
        target_entities = get_target_entities(self._hass, action.action)
        if len(target_entities) > 1:
            return None

        # time range check
        slot_start = string_to_datetime(time_range[0])
        slot_end = string_to_datetime(time_range[1]) if time_range[1] else None
        action_length = action.duration or timedelta(0)
        earliest_action_start = slot_start
        latest_action_start = slot_end - action_length if slot_end else None
        if latest_action_start and latest_action_start < earliest_action_start:
            return None

        # parent action check
        parent_actions = action.parents
        for parent_action in parent_actions:
            parent_action_id = parent_action.action_id
            if not parent_action_id:
                raise ValueError("The parent action does not have an action ID.")
            parent_target_entities = get_target_entities(
                self._hass, parent_action.action
            )
            for parent_entity_id in parent_target_entities:
                if (
                    parent_action_id
                    not in self._lineage_table.lock_queues[parent_entity_id]
                ):
                    raise ValueError(
                        "Parent action {} has not been scheduled on entity {}.".format(
                            parent_action_id, parent_entity_id
                        )
                    )
                parent_action_lock = self._lineage_table.lock_queues[parent_entity_id][
                    parent_action_id
                ]
                if not parent_action_lock:
                    raise ValueError(
                        "Parent action {}'s schedule information on entity {} is missing.".format(
                            parent_action_id, parent_entity_id
                        )
                    )
                parent_action_end_time = string_to_datetime(
                    parent_action_lock.time_range[1]
                )
                if latest_action_start and parent_action_end_time > latest_action_start:
                    return None
                earliest_action_start = max(
                    parent_action_end_time, earliest_action_start
                )

        # serializability check
        action_routine_id = action.routine_id
        if not action_routine_id:  # stand-alone action has no serializability issues
            return datetime_to_string(earliest_action_start)
        action_routine = self._serialization_order[action_routine_id]
        if not action_routine:
            return datetime_to_string(earliest_action_start)
        action_routine_actions = action_routine.actions
        if len(action_routine_actions) == 1:
            # if there is only one action in the routine and
            # only one entity is targeted by the action (already checked at the top),
            # no serializability can be broken by moving up the action
            return datetime_to_string(earliest_action_start)

        # find the routines serialized before this action's routine
        routines_before = []
        for routine_id in self._serialization_order:
            if routine_id == action_routine_id:
                break
            routines_before.append(routine_id)

        # check that the actions scheduled on the entity after the new action end and
        # before the old action start do not belong to routines that are serialized
        # before this action's routine
        old_action_end = string_to_datetime(action_lock.time_range[1])
        for entity_action_id, entity_action_lock in entity_lock_queue.items():
            if not entity_action_lock:
                raise ValueError(
                    "Action {}'s schedule information on entity {} is missing.".format(
                        entity_action_id, entity_id
                    )
                )
            entity_action = entity_action_lock.action
            if string_to_datetime(entity_action_lock.time_range[1]) <= slot_start:
                continue
            if string_to_datetime(entity_action_lock.time_range[0]) >= old_action_end:
                continue
            # check if the action belongs to a routine that is serialized before this
            # action's routine
            entity_routine_id = entity_action.routine_id
            if (
                not entity_routine_id
            ):  # stand-alone action has no serializability issues
                continue
            if entity_routine_id not in routines_before:
                continue
            routine = self._serialization_order[entity_routine_id]
            if not routine:
                raise ValueError(f"Routine {entity_routine_id} has not been scheduled.")
            routine_actions = routine.actions
            if len(routine_actions) > 1:
                return None
            routine_action = list(routine_actions.values())[0]
            target_entities = get_target_entities(self._hass, routine_action.action)
            if len(target_entities) > 1:
                return None

        return datetime_to_string(earliest_action_start)

    async def _find_action_to_fill_slot(
        self, entity_id: str, time_range: tuple[str, str | None]
    ) -> tuple[str | None, str | None]:
        """Find the action that fits the time range and does not break dependencies."""
        best_metric = None
        best_action_id = None
        new_start_time = None
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        for action_id, action_lock in self._lineage_table.lock_queues[
            entity_id
        ].items():
            if not action_lock:
                raise ValueError(
                    "Action {}'s schedule information on entity {} is missing.".format(
                        action_id, entity_id
                    )
                )
            if start_time := self._eligibility_test(entity_id, action_id, time_range):
                if self._resched_policy in (LOCAL_FIRST):
                    return action_id, start_time
                action_length = action_lock.action.duration or timedelta(0)
                if self._resched_policy in (LOCAL_SHORTEST):
                    if not best_metric or action_length < best_metric:
                        best_metric = action_length
                        best_action_id = action_id
                        new_start_time = start_time
                if self._resched_policy in (LOCAL_LONGEST):
                    if not best_metric or action_length > best_metric:
                        best_metric = action_length
                        best_action_id = action_id
                        new_start_time = start_time
        return best_action_id, new_start_time

    async def _fill_slot(
        self,
        entity_id: str,
        action_id: str,
        new_action_start: str,
    ) -> bool:
        """Remove action from current slot and add it to specified slot."""
        action_lock = self._lineage_table.lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )
        action = action_lock.action
        action_length = action.duration or timedelta(0)
        datetime_to_string(string_to_datetime(new_action_start) + action_length)

        # Give back the slot to the free slots
        self._return_free_slot(entity_id, action_id)

        # Remove action from current slot
        self._lineage_table.lock_queues[entity_id].pop(action_id, None)

        # Add action to specified slot
        free_slots = self._lineage_table.free_slots

        new_action_start_dt = string_to_datetime(new_action_start)
        success, _ = self.schedule_all_action(
            action, new_action_start_dt, free_slots, self._lock_leasing
        )
        return success

    async def fill_holes(self, lock_leasing: str) -> LineageTable:
        """Fill all the holes in the free_slots.

        The holes are accessed in a globally-ascending order of time.
        """
        indices = {entity_id: 0 for entity_id in self._lineage_table.free_slots}
        max_indices = {
            entity_id: len(slots) - 1
            for entity_id, slots in self._lineage_table.free_slots.items()
        }
        while any(indices[entity_id] < max_indices[entity_id] for entity_id in indices):
            chosen_time = None
            chosen_entity_ids = list[str]()
            for entity_id, free_slots in self._lineage_table.free_slots.items():
                if indices[entity_id] >= max_indices[entity_id]:
                    continue
                time_range = list(free_slots.items())[indices[entity_id]]
                if not chosen_time or string_to_datetime(time_range[0]) < chosen_time:
                    chosen_time = string_to_datetime(time_range[0])
                    chosen_entity_ids.append(entity_id)
                elif (
                    string_to_datetime(time_range[0]) == chosen_time
                    and chosen_entity_ids
                ):
                    chosen_entity_ids.append(entity_id)

            for entity_id in chosen_entity_ids:
                time_range = list(self._lineage_table.free_slots[entity_id].items())[
                    indices[entity_id]
                ]
                action_id, new_action_start = await self._find_action_to_fill_slot(
                    entity_id, time_range
                )
                if not action_id or not new_action_start:
                    continue
                success = await self._fill_slot(entity_id, action_id, new_action_start)
                if not success:
                    raise ValueError("Failed to fill the free slot.")
                indices[entity_id] += 1
        return self._lineage_table

    async def _find_routine_to_move_up(self) -> str | None:
        """Find a routine that can be moved up."""
        best_metric = 0  # self._calculate_metric()
        best_routine_id = None
        for routine_id, routine in self._serialization_order.items():
            # breadth-first search to find the next action in the routine to move up
            if not routine:
                raise ValueError("Routine %s has not been scheduled." % routine_id)
            next_actions: list[ActionEntity] = []
            for action in list(routine.actions.values())[:-1]:
                if not action.parents:
                    next_actions.append(action)
            for action in next_actions:
                # self._find_slot_to_move_action_up_to(action.action_id)
                next_actions += action.children
            metric = 0  # self._calculate_metric()
            if metric < best_metric:
                best_metric = metric
                best_routine_id = routine_id
        return best_routine_id


class RascalRescheduler:
    """Class responsible for rescheduling entities in Home Assistant.

    This class initializes the rescheduler and provides methods to get the rescheduler
    based on the rescheduling policy.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        lineage_table (LineageTable): The lineage table.
        serialization_order (Queue[str, RoutineEntity]): The serialization order.
        config (ConfigType): The configuration for the rescheduler.

    Attributes:
        _hass (HomeAssistant): The Home Assistant instance.
        _scheduler (RascalScheduler): The Rascal scheduler instance.
        _resched_policy (str): The rescheduling policy.
        _resched_trigger (str): The rescheduling trigger strategy.
        _resched_window (str): The rescheduling window strategy.
        _routine_priority (str): The routine priority strategy.
        _estimation (bool): Flag indicating if estimation is enabled.
        _reschedacc (str): Flag indicating if rescheduling accuracy is enabled.
        _scheduling_policy (str): The scheduling policy.
        _rescheduler (BaseRescheduler): The rescheduler instance.
        _mthresh (float): The M threshold.
        _mithresh (float): The Mi threshold per processor.
        _mis (dict[str, float]): The dictionary of entity IDs and their mis.
    """

    def __init__(
        self, hass: HomeAssistant, scheduler: RascalScheduler, config: ConfigType
    ) -> None:
        """Initialize the rescheduler."""
        self._hass = hass
        self._scheduler = scheduler
        self._resched_policy: str = config[RESCHEDULING_POLICY]
        self._resched_trigger: str = config[RESCHEDULING_TRIGGER]
        self._resched_window: str = config[RESCHEDULING_WINDOW]
        self._routine_priority: str = config[ROUTINE_PRIORITY_POLICY]
        self._estimation: bool = config[RESCHEDULING_ESTIMATION]
        self._resched_accuracy: str = config[RESCHEDULING_ACCURACY]
        self._scheduling_policy: str = config[SCHEDULING_POLICY]
        self._rescheduler = BaseRescheduler(
            self._hass,
            scheduler.lineage_table,
            scheduler.serialization_order,
            self._resched_policy,
            self._routine_priority,
        )
        self._timer_handles: dict[str, tuple[str | None, Callable[[], None] | None]] = {
            entity_id: (None, None)
            for entity_id in scheduler._lineage_table.lock_queues
        }
        if self._estimation:
            self._mthresh: float = config["mthresh"]
            self._mithresh: float = config["mithresh"]
            self._mis = {
                entity_id: 0.0 for entity_id in scheduler._lineage_table.lock_queues
            }

    async def _calc_mi(self, event: Event) -> float:
        """Calculate the entity's new Mi based on the new event."""
        entity_id = event.data.get(ATTR_ENTITY_ID)
        action_id = event.data.get(ATTR_ACTION_ID)
        response = event.data.get(CONF_TYPE)
        time = event.time_fired
        LOGGER.debug(
            "Calculating new Mi for entity %s after action %s's %s response at time %s "
            "in the rescheduler",
            entity_id,
            response,
            action_id,
            datetime_to_string(time),
        )

        if not entity_id or entity_id not in self._scheduler.lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if (
            not action_id
            or action_id not in self._scheduler.lineage_table.lock_queues[entity_id]
        ):
            raise ValueError(
                f"Action {action_id} is not scheduled on entity {entity_id}."
            )
        action_lock = self._scheduler.lineage_table.lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )
        if response == RASC_START:
            scheduled = action_lock.time_range[0]
        elif response == RASC_COMPLETE:
            scheduled = action_lock.time_range[1]
        else:
            return 0
        scheduled_dt = string_to_datetime(scheduled)
        return (time - scheduled_dt).total_seconds()

    async def _calc_m(self, event: Event) -> float:
        """Calculate the M for the schedule."""
        entity_id = event.data.get(ATTR_ENTITY_ID)
        if not entity_id or entity_id not in self._mis:
            return 0
        self._mis[entity_id] = await self._calc_mi(event)
        return min(self._mis.values())

    def _high_mi_entity_ids(self) -> list[str]:
        high_mi_entity_ids = []
        for entity_id, mi in self._mis.items():
            if mi > self._mithresh:
                high_mi_entity_ids.append(entity_id)
        return high_mi_entity_ids

    async def _move_device_schedules(
        self, extra: float = 0.0, time: datetime = datetime.now()
    ) -> bool:
        old_sched = self._scheduler.lineage_table
        self._rescheduler.lineage_table = old_sched
        if self._resched_policy not in (RV, EARLY_START):
            return True
        new_sched = await self._rescheduler.move_device_schedules(extra, time)
        if not new_sched:
            self._apply_schedule(old_sched)
            return False
        self._apply_schedule(new_sched)
        return True

    async def _reschedule(
        self, now: datetime, entity_id: str, action_id: str, diff: timedelta
    ) -> None:
        """Reschedule the entities based on the rescheduling policy."""
        # Save the old schedule
        old_sched = self._scheduler.lineage_table

        if entity_id not in old_sched.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in old_sched.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action_lock = old_sched.lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )

        # change the action's time range. is this the right place?
        st_time, end_time = action_lock.time_range
        old_end_time_dt = string_to_datetime(end_time)
        new_end_time_dt = old_end_time_dt + diff
        new_end_time = datetime_to_string(new_end_time_dt)
        action_lock.time_range = (st_time, new_end_time)

        # Update the rescheduler's schedule to the current one
        self._rescheduler.lineage_table = old_sched
        new_sched = None

        if self._resched_policy in (RV, EARLY_START):
            success = self._move_device_schedules(diff.total_seconds(), now)
        if not success:
            raise ValueError("Failed to move device schedules.")

        if self._resched_policy in (RV):
            new_sched = await self._rescheduler.RV()
        if self._resched_policy in (EARLY_START):
            new_sched = await self._rescheduler.early_start()
        if self._resched_policy in (SJFWO, SJFW):
            affected_source_actions = (
                await self._rescheduler.affected_src_actions_after_len_diff(
                    entity_id, action_id, now
                )
            )
            serializability = self._resched_policy == SJFW
            if serializability:
                immutable_serialization_order = (
                    self._rescheduler.immutable_serialization_order(now)
                )
            (
                descheduled_source_action_ids,
                descheduled_actions,
                affected_entities,
            ) = await self._rescheduler.deschedule_affected_and_later_actions(
                affected_source_actions
            )
            if serializability:
                descheduled_actions = (
                    await self._rescheduler.apply_serialization_order_dependencies(
                        immutable_serialization_order, descheduled_actions
                    )
                )
            new_sched = await self._rescheduler.sjf(
                now,
                descheduled_source_action_ids,
                descheduled_actions,
                affected_entities,
                immutable_serialization_order,
                serializability,
            )
        if not new_sched:
            self._apply_schedule(old_sched)
            return
        self._apply_schedule(new_sched)

    def _apply_schedule(self, schedule: LineageTable) -> None:
        """Apply the new schedule."""
        self._rescheduler.lineage_table = schedule
        self._scheduler.lineage_table = schedule

    def _setup_overtime_check(self, event: Event) -> None:
        """Set up the timer for the rescheduler."""
        if self._resched_trigger in (REACTIVE):
            return
        entity_id: str | None = event.data.get(ATTR_ENTITY_ID)
        action_id: str | None = event.data.get(ATTR_ACTION_ID)
        if not entity_id or entity_id not in self._scheduler.lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        lock_queue = self._scheduler.lineage_table.lock_queues[entity_id]
        if not action_id or action_id not in lock_queue:
            raise ValueError(
                f"Action {action_id} is not scheduled on entity {entity_id}."
            )
        action_lock = lock_queue[action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )
        action = action_lock.action
        expected_action_length = action.duration
        if not expected_action_length:
            return
        timer_delay = expected_action_length * 0.9

        def _get_extra_anticipatory() -> float:
            action_complete = self._scheduler.is_action_complete(action, entity_id)
            if action_complete:
                return 0.0
            action_length = action.duration or timedelta(0)
            extra = action_length.total_seconds() * 0.1
            return extra

        def _get_extra_proactive() -> float:
            rasc: RASC = self._hass.data[DOMAIN]
            action_length_estimate = generate_duration(
                rasc.get_action_length_estimate(
                    entity_id, action.service, action.transition
                )
            )
            if action_length_estimate == expected_action_length:
                return 0.0
            action.duration = action_length_estimate
            extra = (action_length_estimate - expected_action_length).total_seconds()
            return extra

        async def _handle_overtime(event_time: datetime) -> None:
            """Check if the action is about to go on overtime and adjust the schedule."""
            if entity_id not in self._timer_handles:
                raise ValueError("Timer handle for entity %s is missing." % entity_id)
            saved_action_id, _ = self._timer_handles[entity_id]
            if saved_action_id != action_id:
                raise ValueError(
                    "Action ID mismatch for entity %s in the timer handle." % entity_id
                )
            self._timer_handles[entity_id] = None, None

            extra = 0.0
            if self._resched_trigger in (ANTICIPATORY):
                extra = _get_extra_anticipatory()
            elif self._resched_trigger in (PROACTIVE):
                extra = _get_extra_proactive()
            if extra == 0:
                return

            extra_dt = timedelta(seconds=extra)
            await self._reschedule(event_time, entity_id, action_id, extra_dt)

        cancel = async_call_later(self._hass, timer_delay, _handle_overtime)
        self._timer_handles[entity_id] = (action_id, cancel)

    def _cancel_overtime_check(self, event: Event) -> None:
        """Cancel the timer for the rescheduler."""
        entity_id = event.data.get(ATTR_ENTITY_ID)
        action_id = event.data.get(ATTR_ACTION_ID)
        if entity_id in self._timer_handles:
            saved_action_id, saved_cancel = self._timer_handles[entity_id]
            if saved_action_id == action_id and saved_cancel:
                saved_cancel()
                self._timer_handles[entity_id] = None, None

    def _action_length_diff(self, event: Event) -> timedelta:
        """Calculate the difference in action length."""
        entity_id = event.data.get(ATTR_ENTITY_ID)
        action_id = event.data.get(ATTR_ACTION_ID)
        if not entity_id:
            raise ValueError("Entity ID is missing.")
        if entity_id not in self._scheduler.lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if not action_id:
            raise ValueError("Action ID is missing.")
        if action_id not in self._scheduler.lineage_table.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} is not scheduled on entity {entity_id}."
            )
        action_lock = self._scheduler.lineage_table.lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )
        exp_end_time = string_to_datetime(action_lock.time_range[1])
        act_end_time = event.time_fired
        return act_end_time - exp_end_time

    async def _handle_undertime(self, event: Event) -> None:
        self._cancel_overtime_check(event)
        diff = self._action_length_diff(event)
        entity_id: str | None = event.data.get(ATTR_ENTITY_ID)
        action_id: str | None = event.data.get(ATTR_ACTION_ID)
        if not entity_id or not action_id:
            raise ValueError("Entity ID or action ID is missing in the event.")
        await self._reschedule(event.time_fired, entity_id, action_id, diff)

    async def handle_event(self, event: Event) -> None:
        """Handle RASC events. This is called by the scheduler."""

        LOGGER.debug("Handling RASC event in the rescheduler")
        if self._scheduling_policy not in (TIMELINE):
            return
        response = event.data.get(CONF_TYPE)
        if response not in (RASC_START, RASC_COMPLETE):
            return
        if response == RASC_START:
            self._setup_overtime_check(event)
        elif response == RASC_COMPLETE:
            await self._handle_undertime(event)
