"""Resource reclamation and rescheduling for RASC."""
import asyncio
import logging

from homeassistant.const import (
    ATTR_ACTION_ID,
    ATTR_ENTITY_ID,
    CONF_TYPE,
    EARLY_START,
    RASC_COMPLETE,
    RASC_START,
    RESCHEDULE_ALL,
    RESCHEDULE_SOME,
    RESCHEDULING_ACCURACY,
    RESCHEDULING_ESTIMATION,
    RESCHEDULING_POLICY,
    RV,
    SCHEDULING_POLICY,
    TIMELINE,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .scheduler import (
    BaseScheduler,
    LineageTable,
    datetime_to_string,
    string_to_datetime,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


class BaseRescheduler(BaseScheduler):
    """Base class for rescheduling resources.

    This class is responsible for rescheduling resources based on the rescheduling policy.
    It is triggered every time an action RASC response is received.
    """

    # for each action in the lineage table, action.parents is its dependencies
    # i need a global lineage table that keeps track of all the dependencies
    # also, in case there is no estimation, explore the dependencies between actions to find the best action to swap:
    # Myopic First fit: Look at next command to start or the first command that fits the whole
    # Myopic Best fit: for this device find the best action to swap based on a one device only metric
    # Global best fit: look across all devices and optimize a global metric

    async def reschedule_device(self, entity_id: str) -> LineageTable:
        """Reschedule resources for a device."""
        raise NotImplementedError

    async def reschedule_some(self, entity_ids: list[str]) -> LineageTable:
        """Reschedule resources only for devices that exceed the Mi threshold.

        Move schedule backward or forward for the rest of the devices.
        """
        raise NotImplementedError

    async def reschedule_all(self) -> LineageTable:
        """Reschedule resources for all devices.

        From the serialization order, figure out which routines have been scheduled.
        Reschedule all routines that have been scheduled but are not executing before rescheduling is done.
        """
        raise NotImplementedError


class RVRescheduler(BaseRescheduler):
    """Reschedule resources using the RV algorithm."""

    def __init__(
        self,
        hass: HomeAssistant,
        lineage_table: LineageTable,
    ) -> None:
        """Initialize jit scheduler."""
        self._hass = hass
        self._lineage_table = lineage_table

    async def reschedule_device(self, entity_id: str) -> LineageTable:
        """Reschedule resources for a device."""
        _LOGGER.info("Rescheduling device %s using the RV algorithm", entity_id)
        raise NotImplementedError

    async def reschedule_some(self, entity_ids: list[str]) -> LineageTable:
        """Reschedule resources for a set of devices."""
        _LOGGER.info(
            "Rescheduling devices %s using the RV algorithm", ", ".join(entity_ids)
        )
        raise NotImplementedError

    async def reschedule_all(self) -> LineageTable:
        """Reschedule resources for all devices."""
        _LOGGER.info("Rescheduling all devices using the RV algorithm")
        raise NotImplementedError


class ESRescheduler(BaseRescheduler):
    """Reschedule resources using the Early Start algorithm."""

    def __init__(
        self,
        hass: HomeAssistant,
        lineage_table: LineageTable,
    ) -> None:
        """Initialize jit scheduler."""
        self._hass = hass
        self._lineage_table = lineage_table

    async def reschedule_device(self, entity_id: str) -> LineageTable:
        """Reschedule resources for a device."""
        _LOGGER.info(
            "Rescheduling device %s using the Early Start algorithm", entity_id
        )
        raise NotImplementedError

    async def reschedule_some(self, entity_ids: list[str]) -> LineageTable:
        """Reschedule resources for a set of devices."""
        _LOGGER.info(
            "Rescheduling devices %s using the RV algorithm", ", ".join(entity_ids)
        )
        raise NotImplementedError

    async def reschedule_all(self) -> LineageTable:
        """Reschedule resources for a device."""
        _LOGGER.info("Rescheduling all devices using the Early Start algorithm")
        raise NotImplementedError


class RascalRescheduler:
    """Class responsible for rescheduling entities in Home Assistant.

    This class initializes the rescheduler and provides methods to get the rescheduler
    based on the rescheduling policy.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        lineage_table (LineageTable): The lineage table.
        config (ConfigType): The configuration for the rescheduler.

    Attributes:
        _hass (HomeAssistant): The Home Assistant instance.
        _lineage_table (LineageTable): The lineage table.
        _reschedpolicy (str): The rescheduling policy.
        _estimation (bool): Flag indicating if estimation is enabled.
        _reschedacc (bool): Flag indicating if rescheduling accuracy is enabled.
        _scheduling_policy (str): The scheduling policy.
        _rescheduler (_RT): The rescheduler instance.
        _mthresh (int): The maximum threshold.
        _mithresh (int): The minimum threshold.
        _mis (dict[str, int]): The dictionary of entity IDs and their miscounts.
    """

    def __init__(
        self, hass: HomeAssistant, lineage_table: LineageTable, config: ConfigType
    ) -> None:
        """Initialize the rescheduler."""
        self._hass = hass
        self._lineage_table = lineage_table
        self._reschedpolicy = config[RESCHEDULING_POLICY]
        self._estimation = config[RESCHEDULING_ESTIMATION]
        self._reschedacc = config[RESCHEDULING_ACCURACY]
        self._scheduling_policy = config[SCHEDULING_POLICY]
        self._rescheduler = self._get_rescheduler()
        if self._estimation:
            self._mthresh: float = config["mthresh"]
            self._mithresh: float = config["mithresh"]
            self._mis: dict[str, float] = {
                entity_id: 0.0 for entity_id in self._lineage_table.lock_queues
            }

    def _get_rescheduler(self) -> BaseRescheduler | None:
        if self._reschedpolicy == RV:
            return RVRescheduler(self._hass, self._lineage_table)
        if self._reschedpolicy == EARLY_START:
            return ESRescheduler(self._hass, self._lineage_table)
        return None

    async def move_device_schedule(self, entity_id: str, m: float) -> LineageTable:
        """Move the schedule of a device by m milliseconds."""
        raise NotImplementedError

    async def move_device_schedules(self, m: float) -> LineageTable:
        """Move the schedule of devices that do not exceed the Mi threshold."""
        tasks = []
        for entity_id in self._mis:
            if self._mis[entity_id] <= self._mithresh:
                tasks.append(
                    asyncio.create_task(self.move_device_schedule(entity_id, m))
                )
        for task in tasks:
            await task
        return self._lineage_table

    async def _reschedule_device(self, entity_id: str) -> LineageTable:
        if not self._rescheduler:
            raise ValueError("Rescheduler object should be set up by now.")
        return await self._rescheduler.reschedule_device(entity_id)

    async def _reschedule_some(self, entity_ids: list[str]) -> LineageTable:
        if not self._rescheduler:
            raise ValueError("Rescheduler object should be set up by now.")
        return await self._rescheduler.reschedule_some(entity_ids)

    async def _reschedule_all(self) -> LineageTable:
        if not self._rescheduler:
            raise ValueError("Rescheduler object should be set up by now.")
        return await self._rescheduler.reschedule_all()

    async def calc_mi(self, event: Event) -> float:
        """Calculate the entity's new Mi based on the new event."""
        entity_id = event.data.get(ATTR_ENTITY_ID)
        action_id = event.data.get(ATTR_ACTION_ID)
        response = event.data.get(CONF_TYPE)
        time = event.time_fired
        _LOGGER.debug(
            "Handling response %s for action %s on "
            "entity %s at time %s in the rescheduler",
            response,
            action_id,
            entity_id,
            datetime_to_string(time),
        )

        if not entity_id or entity_id not in self._lineage_table.lock_queues:
            return 0
        if not action_id or action_id not in self._lineage_table.lock_queues[entity_id]:
            return 0
        action_lock = self._lineage_table.lock_queues[entity_id][action_id]
        if not action_lock:
            return 0
        if response == RASC_START:
            scheduled = action_lock.time_range[0]
        elif response == RASC_COMPLETE:
            scheduled = action_lock.time_range[1]
        else:
            return 0
        scheduled_dt = string_to_datetime(scheduled)
        return (time - scheduled_dt).total_seconds()

    async def calc_m(self, event: Event) -> float:
        """Calculate the M for the schedule."""
        entity_id = event.data.get(ATTR_ENTITY_ID)
        if not entity_id or entity_id not in self._mis:
            return 0
        self._mis[entity_id] = await self.calc_mi(event)
        return min(self._mis.values())

    def _high_mi_entity_ids(self) -> list[str]:
        high_mi_entity_ids = []
        for entity_id, mi in self._mis.items():
            if mi > self._mithresh:
                high_mi_entity_ids.append(entity_id)
        return high_mi_entity_ids

    async def handle_event(self, event: Event) -> None:
        """Handle RASC events. This is called by the scheduler."""

        _LOGGER.debug("Handling RASC event in the rescheduler")
        response = event.data.get(CONF_TYPE)
        if response in (RASC_START, RASC_COMPLETE):
            if self._scheduling_policy in (TIMELINE) and self._estimation is True:
                m = await self.calc_m(event)
                if m > self._mthresh:
                    if self._reschedacc in (RESCHEDULE_ALL):
                        await self._reschedule_all()
                    elif self._reschedacc in (RESCHEDULE_SOME):
                        await self._reschedule_some(self._high_mi_entity_ids())
                else:
                    await self.move_device_schedules(m)
            elif self._scheduling_policy in (TIMELINE) and self._estimation is False:
                if response == RASC_COMPLETE:
                    entity_id = event.data.get(ATTR_ENTITY_ID)
                    if entity_id:
                        await self._reschedule_device(entity_id)
