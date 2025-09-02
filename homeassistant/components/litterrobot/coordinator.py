"""The Litter-Robot coordinator."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
import logging

from pylitterbot import Account, FeederRobot, LitterRobot
from pylitterbot.robot.litterrobot4 import LitterRobot4
from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import storage
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=5)

type LitterRobotConfigEntry = ConfigEntry[LitterRobotDataUpdateCoordinator]


class LitterRobotDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """The Litter-Robot data update coordinator."""

    config_entry: LitterRobotConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: LitterRobotConfigEntry
    ) -> None:
        """Initialize the Litter-Robot data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        self.account = Account(websession=async_get_clientsession(hass))
        # Per-robot hopper metrics and last seen event timestamp
        self.hopper_metrics: dict[str, dict[str, float | int | None]] = {}
        self._last_hopper_event_ts: dict[str, float] = {}
        self._hopper_totals: dict[str, float] = {}
        self._store: storage.Store | None = None

    async def _async_update_data(self) -> None:
        """Update all device states from the Litter-Robot API."""
        await self.account.refresh_robots()
        await self.account.load_pets()
        for pet in self.account.pets:
            # Need to fetch weight history for `get_visits_since`
            await pet.fetch_weight_history()

        # Update LR4 hopper metrics and fire events for new dispenses
        updated_persist = False
        for robot in (r for r in self.account.robots if isinstance(r, LitterRobot4)):
            try:
                activities = await robot.get_activity_history(limit=50)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Failed fetching activity for %s: %s", robot.serial, err)
                continue

            today_start = dt_util.start_of_local_day()
            # Normalize to monotonic increasing events
            hopper_events = [
                a for a in activities if str(a.action).startswith("Litter Dispensed")
            ]
            hopper_events.sort(key=lambda a: a.timestamp)

            # Fire events for new activities
            last_ts = self._last_hopper_event_ts.get(robot.serial, 0.0)
            newest_ts = last_ts
            for ev in hopper_events:
                ev_ts = ev.timestamp.timestamp() if hasattr(ev.timestamp, "timestamp") else 0.0
                # Parse numeric value from "Litter Dispensed: <value>"
                value_str = str(ev.action).split(":", 1)[-1].strip() if ":" in str(ev.action) else None
                try:
                    value = float(value_str) if value_str is not None else None
                except ValueError:
                    value = None
                if ev_ts > last_ts:
                    self.hass.bus.async_fire(
                        "litterrobot_hopper_dispensed",
                        {
                            "serial": robot.serial,
                            "name": robot.name,
                            "timestamp": ev.timestamp.isoformat(),
                            "value": value,
                        },
                    )
                    if value is not None:
                        total = self._hopper_totals.get(robot.serial, 0.0) + value
                        self._hopper_totals[robot.serial] = total
                        updated_persist = True
                if ev_ts > newest_ts:
                    newest_ts = ev_ts
            if newest_ts > 0:
                if self._last_hopper_event_ts.get(robot.serial) != newest_ts:
                    self._last_hopper_event_ts[robot.serial] = newest_ts
                    updated_persist = True

            # Compute daily metrics
            sum_today = 0.0
            count_today = 0
            last_value: float | None = None
            if hopper_events:
                # Last event value
                last_ev = hopper_events[-1]
                lv_str = str(last_ev.action).split(":", 1)[-1].strip() if ":" in str(last_ev.action) else None
                try:
                    last_value = float(lv_str) if lv_str is not None else None
                except ValueError:
                    last_value = None
            for ev in hopper_events:
                if ev.timestamp >= today_start:
                    count_today += 1
                    val_str = str(ev.action).split(":", 1)[-1].strip() if ":" in str(ev.action) else None
                    try:
                        sum_today += float(val_str) if val_str is not None else 0.0
                    except ValueError:
                        pass

            self.hopper_metrics[robot.serial] = {
                "sum_today": sum_today,
                "count_today": count_today,
                "last_value": last_value,
                "total": self._hopper_totals.get(robot.serial, 0.0),
            }

        if updated_persist and self._store is not None:
            await self._store.async_save(
                {
                    "last_ts": self._last_hopper_event_ts,
                    "totals": self._hopper_totals,
                }
            )

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            # Load persisted hopper totals and last timestamps
            self._store = storage.Store(self.hass, 1, f"{DOMAIN}_hopper_metrics")
            stored = await self._store.async_load() or {}
            self._last_hopper_event_ts = stored.get("last_ts", {})
            self._hopper_totals = stored.get("totals", {})

            await self.account.connect(
                username=self.config_entry.data[CONF_USERNAME],
                password=self.config_entry.data[CONF_PASSWORD],
                load_robots=True,
                subscribe_for_updates=True,
                load_pets=True,
            )
        except LitterRobotLoginException as ex:
            raise ConfigEntryAuthFailed("Invalid credentials") from ex
        except LitterRobotException as ex:
            raise UpdateFailed("Unable to connect to Litter-Robot API") from ex

    def litter_robots(self) -> Generator[LitterRobot]:
        """Get Litter-Robots from the account."""
        return (
            robot for robot in self.account.robots if isinstance(robot, LitterRobot)
        )

    def feeder_robots(self) -> Generator[FeederRobot]:
        """Get Feeder-Robots from the account."""
        return (
            robot for robot in self.account.robots if isinstance(robot, FeederRobot)
        )
