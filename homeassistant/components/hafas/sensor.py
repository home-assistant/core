"""Sensor for HaFAS."""

from __future__ import annotations

from datetime import timedelta
import functools
from typing import Any

from pyhafas import HafasClient
from pyhafas.types.fptf import Journey, Station

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_OFFSET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import CONF_DESTINATION, CONF_ONLY_DIRECT, CONF_START, DOMAIN

ICON = "mdi:train"
SCAN_INTERVAL = timedelta(minutes=2)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up HaFAS sensor entities based on a config entry."""
    client: HafasClient = hass.data[DOMAIN][entry.entry_id]

    # Already verified to have at least one entry in config_flow.py
    start_station = (
        await hass.async_add_executor_job(client.locations, entry.data[CONF_START])
    )[0]
    destination_station = (
        await hass.async_add_executor_job(
            client.locations, entry.data[CONF_DESTINATION]
        )
    )[0]

    offset = timedelta(**entry.data[CONF_OFFSET])

    async_add_entities(
        [
            HaFAS(
                hass,
                client,
                start_station,
                destination_station,
                offset,
                entry.data[CONF_ONLY_DIRECT],
                entry.title,
                entry.entry_id,
            )
        ],
        True,
    )


class HaFAS(SensorEntity):
    """Implementation of a HaFAS sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: HafasClient,
        start_station: Station,
        destination_station: Station,
        offset: timedelta,
        only_direct: bool,
        title: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self.client = client
        self.origin = start_station
        self.destination = destination_station
        self.offset = offset
        self.only_direct = only_direct
        self._name = title

        self._attr_unique_id = entry_id

        self.journeys: list[Journey] = []

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon for the frontend."""
        return ICON

    @property
    def native_value(self) -> str:
        """Return the departure time of the next train."""
        if (
            len(self.journeys) == 0
            or self.journeys[0].legs is None
            or len(self.journeys[0].legs) == 0
        ):
            return "No connection possible"

        first_leg = self.journeys[0].legs[0]

        value = first_leg.departure.strftime("%H:%M")
        if (
            first_leg.departureDelay is not None
            and first_leg.departureDelay != timedelta()
        ):
            delay = int(first_leg.departureDelay.total_seconds() // 60)

            value += f" + {delay}"

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if (
            len(self.journeys) == 0
            or self.journeys[0].legs is None
            or len(self.journeys[0].legs) == 0
        ):
            return {}

        journey = self.journeys[0]
        first_leg = journey.legs[0]
        last_leg = journey.legs[-1]
        products = ", ".join([x.name for x in journey.legs if x.name is not None])[:-2]
        duration = timedelta() if journey.duration is None else journey.duration
        delay = (
            timedelta()
            if first_leg.departureDelay is None
            else first_leg.departureDelay
        )
        delay_arrival = (
            timedelta() if last_leg.arrivalDelay is None else last_leg.arrivalDelay
        )

        connections = {
            "departure": first_leg.departure,
            "arrival": last_leg.arrival,
            "transfers": len(journey.legs) - 1,
            "time": str(duration),
            "products": products,
            "ontime": delay == timedelta(),
            "delay": str(delay),
            "canceled": first_leg.cancelled,
            "delay_arrival": str(delay_arrival),
        }

        next_connection = "No connection possible"
        if (
            len(self.journeys) > 1
            and self.journeys[1].legs is not None
            and len(self.journeys[1].legs) > 0
        ):
            next_connection = self.journeys[1].legs[0].departure

        connections["next"] = next_connection

        next_on_connection = "No connection possible"
        if (
            len(self.journeys) > 2
            and self.journeys[2].legs is not None
            and len(self.journeys[2].legs) > 0
        ):
            next_on_connection = self.journeys[2].legs[0].departure

        connections["next_on"] = next_on_connection

        return connections

    async def async_update(self) -> None:
        """Update the journeys using pyhafas."""

        self.journeys = await self.hass.async_add_executor_job(
            functools.partial(
                self.client.journeys,
                origin=self.origin,
                destination=self.destination,
                date=dt_util.as_local(dt_util.utcnow() + self.offset),
                max_changes=0 if self.only_direct else -1,
                max_journeys=3,
            )
        )
