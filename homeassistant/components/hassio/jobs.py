"""Track Supervisor job data and allow subscription to updates."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
import logging
from typing import Any
from uuid import UUID

from aiohasupervisor.models import Job

from homeassistant.core import (
    CALLBACK_TYPE,
    HomeAssistant,
    callback,
    is_callback_check_partial,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_DATA,
    ATTR_STARTUP,
    ATTR_UPDATE_KEY,
    ATTR_WS_EVENT,
    EVENT_JOB,
    EVENT_SUPERVISOR_EVENT,
    EVENT_SUPERVISOR_UPDATE,
    STARTUP_COMPLETE,
    UPDATE_KEY_SUPERVISOR,
)
from .handler import get_supervisor_client

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class JobSubscription:
    """Subscribe for updates on jobs which match filters.

    UUID is preferred match but only available in cases of a background API that
    returns the UUID before taking the action. Others are used to match jobs only
    if UUID is omitted. Either name or UUID is required to be able to match.

    event_callback must be safe annotated as a homeassistant.core.callback
    and safe to call in the event loop.
    """

    event_callback: Callable[[Job], Any]
    uuid: str | None = None
    name: str | None = None
    reference: str | None = None

    def __post_init__(self) -> None:
        """Validate at least one filter option is present."""
        if not self.name and not self.uuid:
            raise ValueError("Either name or uuid must be provided!")
        if not is_callback_check_partial(self.event_callback):
            raise ValueError("event_callback must be a homeassistant.core.callback!")

    def matches(self, job: Job) -> bool:
        """Return true if job matches subscription filters."""
        if self.uuid:
            return job.uuid == self.uuid
        return job.name == self.name and self.reference in (None, job.reference)


class SupervisorJobs:
    """Manage access to Supervisor jobs."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize object."""
        self._hass = hass
        self._supervisor_client = get_supervisor_client(hass)
        self._jobs: dict[UUID, Job] = {}
        self._subscriptions: set[JobSubscription] = set()
        self._dispatcher_disconnect: Callable[[], None] | None = None

    @property
    def current_jobs(self) -> list[Job]:
        """Return current jobs."""
        return list(self._jobs.values())

    def subscribe(self, subscription: JobSubscription) -> CALLBACK_TYPE:
        """Subscribe to updates for job. Return callback is used to unsubscribe.

        If any jobs match the subscription at the time this is called, runs the
        callback on them.
        """
        self._subscriptions.add(subscription)

        # Run the callback on each existing match
        # We catch all errors to prevent an error in one from stopping the others
        for match in [job for job in self._jobs.values() if subscription.matches(job)]:
            try:
                return subscription.event_callback(match)
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "Error encountered processing Supervisor Job (%s %s %s) - %s",
                    match.name,
                    match.reference,
                    match.uuid,
                    err,
                )

        return partial(self._subscriptions.discard, subscription)

    async def refresh_data(self, first_update: bool = False) -> None:
        """Refresh job data."""
        job_data = await self._supervisor_client.jobs.info()
        job_queue: list[Job] = job_data.jobs.copy()
        new_jobs: dict[UUID, Job] = {}
        changed_jobs: list[Job] = []

        # Rebuild our job cache from new info and compare to find changes
        while job_queue:
            job = job_queue.pop(0)
            job_queue.extend(job.child_jobs)
            job = replace(job, child_jobs=[])

            if job.uuid not in self._jobs or job != self._jobs[job.uuid]:
                changed_jobs.append(job)
                new_jobs[job.uuid] = replace(job, child_jobs=[])

        # For any jobs that disappeared which weren't done, tell subscribers they
        # changed to done. We don't know what else happened to them so leave the
        # rest of their state as is rather then guessing
        changed_jobs.extend(
            [
                replace(job, done=True)
                for uuid, job in self._jobs.items()
                if uuid not in new_jobs and job.done is False
            ]
        )

        # Replace our cache and inform subscribers of all changes
        self._jobs = new_jobs
        for job in changed_jobs:
            self._process_job_change(job)

        # If this is the first update register to receive Supervisor events
        if first_update:
            self._dispatcher_disconnect = async_dispatcher_connect(
                self._hass, EVENT_SUPERVISOR_EVENT, self._supervisor_events_to_jobs
            )

    @callback
    def _supervisor_events_to_jobs(self, event: dict[str, Any]) -> None:
        """Update job data cache from supervisor events."""
        if ATTR_WS_EVENT not in event:
            return

        if (
            event[ATTR_WS_EVENT] == EVENT_SUPERVISOR_UPDATE
            and event.get(ATTR_UPDATE_KEY) == UPDATE_KEY_SUPERVISOR
            and event.get(ATTR_DATA, {}).get(ATTR_STARTUP) == STARTUP_COMPLETE
        ):
            self._hass.async_create_task(self.refresh_data())

        elif event[ATTR_WS_EVENT] == EVENT_JOB:
            job = Job.from_dict(event[ATTR_DATA] | {"child_jobs": []})
            self._jobs[job.uuid] = job
            self._process_job_change(job)

    def _process_job_change(self, job: Job) -> None:
        """Process a job change by triggering callbacks on subscribers."""
        for sub in self._subscriptions:
            if sub.matches(job):
                sub.event_callback(job)

        # If the job is done, pop it from our cache if present after processing is done
        if job.done and job.uuid in self._jobs:
            del self._jobs[job.uuid]

    @callback
    def unload(self) -> None:
        """Unregister with dispatcher on config entry unload."""
        if self._dispatcher_disconnect:
            self._dispatcher_disconnect()
            self._dispatcher_disconnect = None
