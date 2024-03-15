"""Support for rasc."""
from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
from typing import TYPE_CHECKING

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
                "start_time": action_info.time_range[0],
                "end_time": action_info.time_range[1],
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


def output_all(
    logger: logging.Logger,
    locks: dict[str, str | None] | None = None,
    lock_queues: dict[str, Queue] | None = None,
    free_slots: dict[str, Queue] | None = None,
    serialization_order: Queue | None = None,
    wait_queue: Queue | None = None,
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
