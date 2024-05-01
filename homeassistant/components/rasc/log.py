"""Support for rasc."""
from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .entity import Queue


class Trial:
    """A class for recording trail."""

    def __init__(self):
        """Initialize the trail."""
        self.num = 0

    def increment(self):
        """Increase the trail."""
        self.num += 1


trail = Trial()


def set_log_dir() -> str:
    """Set log path."""
    fp = "testrun-" + datetime.datetime.now().strftime("%Y-%m-%d")

    if os.path.isdir(fp):
        shutil.rmtree(fp)
    os.mkdir(fp)

    return fp


_LOG_PATH = set_log_dir()


def set_logger() -> logging.Logger:
    """Set logger."""
    logger = logging.getLogger("rascal_logger")
    logger.setLevel(logging.DEBUG)
    log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    filename = os.path.join(_LOG_PATH, "rascal.log")
    log_handler = logging.FileHandler(filename, mode="w")
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)
    return logger


def output_lock_queues(lock_queues: dict[str, Queue], filepath: str) -> None:
    """Output the lock queues."""
    fp = os.path.join(filepath, "locks_queues.json")
    lock_queues_list = []
    for entity_id, actions in lock_queues.items():
        action_list = []
        for action_id, action_info in actions.items():
            sub_entity_json = {
                "action_id": action_id,
                "action_state": action_info.action_state,
                "lock_state": action_info.lock_state,
                "start_time": action_info.start_time,
                "end_time": action_info.end_time,
            }
            action_list.append(sub_entity_json)

        entity_json = {"entity_id": entity_id, "actions": action_list}

        lock_queues_list.append(entity_json)

    out = {"Type": "Lock Queues", "Lock Queues": lock_queues_list}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # print(json.dumps(out, indent=2))  # noqa: T201


def output_locks(locks: dict[str, str | None], filepath: str) -> None:
    """Output the locks."""
    fp = os.path.join(filepath, "locks.json")

    locks_list = []
    for entity_id, routine_id in locks.items():
        entity_json = {"entity_id": entity_id, "routine_id": routine_id}
        locks_list.append(entity_json)

    out = {"Type": "Locks", "Locks": locks_list}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # print(json.dumps(out, indent=2))  # noqa: T201


def output_wait_queues(wait_queue: Queue, filepath: str) -> None:
    """Output wait queues."""
    fp = os.path.join(filepath, "wait_queue.json")
    routines: list[str] = []
    for routine_id, _ in wait_queue.items():
        routines.append(routine_id)

    out = {"Type": "Wait Queue", "Wait Queue": routines}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # print(json.dumps(out, indent=2))  # noqa: T201


def output_lock_waitlist(lock_waitlist: dict[str, list[str]], filepath: str) -> None:
    """Output lock waitlist."""
    fp = os.path.join(filepath, "lock_waitlist.json")

    waitlist = []
    for entity_id, routines in lock_waitlist.items():
        routine_list = []
        for routine_id in routines:
            routine_list.append(routine_id)

        entity_json = {"entity_id": entity_id, "waitlist": routine_list}

        waitlist.append(entity_json)

    out = {"Type": "Lock Waitlist", "Routines": waitlist}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def output_serialization_order(serialization_order: Queue, filepath: str) -> None:
    """Output serialization order."""
    fp = os.path.join(filepath, "serialization_order.json")
    routines: list[str] = []
    for routine_id, _ in serialization_order.items():
        routines.append(routine_id)

    out = {"Type": "Serialization Order", "Serialization Order": routines}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # print(json.dumps(out, indent=2))  # noqa: T201()


def output_free_slots(timelines: dict[str, Queue], filepath: str) -> None:
    """Output free slots."""
    fp = os.path.join(filepath, "free_slots.json")

    tl = []
    for entity_id, timeline in timelines.items():
        slot_list = []
        for st, end in timeline.items():
            sub_entity_json = {"st": st, "end": end}

            slot_list.append(sub_entity_json)

        entity_json = {"entity_id": entity_id, "timeline": slot_list}

        tl.append(entity_json)

    out = {"Type": "Free Slots", "Free Slots": tl}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # print(json.dumps(out, indent=2))  # noqa: T201()


def output_routine(routine_id: str, actions: dict[str, Any]) -> None:
    """Output routine."""
    dirname = f"trail-{trail.num:04d}"
    trail.increment()

    os.path.join(_LOG_PATH, dirname, "routines.json")

    action_list = []
    for _, entity in actions.items():
        parents = []
        children = []

        for parent in entity.parents:
            parents.append(parent.action_id)

        for child in entity.children:
            children.append(child.action_id)

        entity_json = {
            "action_id": entity.action_id,
            "action": entity.action,
            "action_completed": entity.action_completed,
            "parents": parents,
            "children": children,
            "delay": str(entity.delay),
            "duration": str(entity.duration),
        }

        action_list.append(entity_json)

    out = {"Routine_id": routine_id, "Actions": action_list}

    print(json.dumps(out, indent=2))  # noqa: T201


def output_preset(preset: set[str], filepath: str) -> None:
    """Output serialization order."""
    fp = os.path.join(filepath, "preset.json")
    routines: list[str] = []
    for routine_id in preset:
        routines.append(routine_id)

    out = {"Type": "Preset", "Routines": routines}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def output_postset(postset: set[str], filepath: str) -> None:
    """Output serialization order."""
    fp = os.path.join(filepath, "postset.json")
    routines: list[str] = []
    for routine_id in postset:
        routines.append(routine_id)

    out = {"Type": "Postset", "Routines": routines}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def output_all(
    logger: logging.Logger,
    locks: dict[str, str | None] | None = None,
    lock_queues: dict[str, Queue] | None = None,
    free_slots: dict[str, Queue] | None = None,
    serialization_order: Queue | None = None,
    wait_queue: Queue | None = None,
    lock_waitlist: dict[str, list[str]] | None = None,
    preset: set[str] | None = None,
    postset: set[str] | None = None,
):
    """Output specific info."""

    dirname = f"trail-{trail.num:04d}"
    trail.increment()

    fp = os.path.join(_LOG_PATH, dirname)
    logger.debug("Output logs to %s.", fp)

    if not os.path.isdir(fp):
        os.mkdir(fp)

    if locks:
        output_locks(locks, fp)

    if lock_queues:
        output_lock_queues(lock_queues, fp)

    if free_slots:
        output_free_slots(free_slots, fp)

    if serialization_order:
        output_serialization_order(serialization_order, fp)

    if wait_queue:
        output_wait_queues(wait_queue, fp)

    if lock_waitlist:
        output_lock_waitlist(lock_waitlist, fp)

    if preset:
        output_preset(preset, fp)

    if postset:
        output_postset(postset, fp)
