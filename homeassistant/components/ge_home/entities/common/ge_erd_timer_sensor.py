import asyncio
from datetime import timedelta
from typing import Optional
import logging
import async_timeout

from gehomesdk import ErdCode, ErdCodeType, ErdCodeClass, ErdMeasurementUnits

from .ge_erd_sensor import GeErdSensor
from ...devices import ApplianceApi


_LOGGER = logging.getLogger(__name__)

class GeErdTimerSensor(GeErdSensor):
    """GE Entity for timer sensors"""

    async def set_timer(self, duration: timedelta):
        try:
            await self.appliance.async_set_erd_value(self.erd_code, duration)
        except:
            _LOGGER.warn("Could not set timer value", exc_info=1)

    async def clear_timer(self):
        try:
            #There's a stupid issue in that if the timer has already expired, the beeping
            #won't turn off... I don't see any way around it though.
            await self.appliance.async_set_erd_value(self.erd_code, timedelta(seconds=0))
        except:
            _LOGGER.warn("Could not clear timer value", exc_info=1)
