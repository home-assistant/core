"""Data update coordinator for the Proximity integration."""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
import logging
import math
from typing import cast

from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_ZONE,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util.location import distance

from .const import (
    ATTR_DIR_OF_TRAVEL,
    ATTR_DIST_TO,
    ATTR_IN_IGNORED_ZONE,
    ATTR_NEAREST,
    ATTR_SPEED,
    CONF_IGNORED_ZONES,
    CONF_SPEED_THRESHOLD,
    CONF_TOLERANCE,
    CONF_TRACKED_ENTITIES,
    DEFAULT_DIR_OF_TRAVEL,
    DEFAULT_DIST_TO_ZONE,
    DEFAULT_NEAREST,
    DEFAULT_SPEED_THRESHOLD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# -- Earth geometry -------------------------------------------------------------
_EARTH_RADIUS_M: float = 6_371_000.0

# -- Movement window tuning -----------------------------------------------------

# Number of position samples retained per entity (sliding window).
POSITION_WINDOW_SIZE: int = 8

# cos(60°): minimum |cosine| of the angle between v_move and v_zone for the
# direction to be resolved as 'towards' or 'away_from'.  When the angle exceeds
# 60° (movement roughly perpendicular to the zone vector) the last valid
# direction is preserved instead.
DOT_THRESHOLD_COS: float = 0.5

# Minimum seconds after which a stationary synthetic sample is injected.  This causes
# speed to decay toward 0 and the entity to become 'stationary' when no real
# GPS updates arrive (decay mechanism).
STALE_THRESHOLD_S_MIN: float = 120.0

# Maximum seconds after which a stationary synthetic sample is injected.  This causes
# speed to decay toward 0 and the entity to become 'stationary' when no real
# GPS updates arrive (decay mechanism).
STALE_THRESHOLD_S_MAX: float = 900.0

# Maximum age of samples to consider for speed calculation.
SPEED_WINDOW_MAX_AGE_S: float = 900.0

# -- Type alias -----------------------------------------------------------------
type ProximityConfigEntry = ConfigEntry["ProximityDataUpdateCoordinator"]


# -- Data structures ------------------------------------------------------------


@dataclass
class PositionSample:
    """A single position sample with its wall-clock timestamp."""

    timestamp: datetime
    latitude: float
    longitude: float


@dataclass
class EntityMovementState:
    """Internal movement state for one tracked entity.

    Persists across coordinator refreshes; not exposed directly to sensors.
    """

    samples: deque[PositionSample] = field(
        default_factory=lambda: deque(maxlen=POSITION_WINDOW_SIZE)
    )
    distance_to_zone: int | None = None
    speed: float | None = None
    direction: str | None = None
    in_ignored_zone: bool = False

    def update_period(self) -> float:
        """Return the mean update period (seconds) between samples, clamped between STALE_THRESHOLD_S_MIN and STALE_THRESHOLD_S_MAX.

        Returns STALE_THRESHOLD_S_MAX if there are fewer than 2 samples.
        """
        if len(self.samples) < 2:
            return STALE_THRESHOLD_S_MAX
        # Allow for some jitter beyond the threshold.
        return max(
            min(
                1.1
                * (
                    self.samples[-1].timestamp - self.samples[0].timestamp
                ).total_seconds()
                / (len(self.samples) - 1),
                STALE_THRESHOLD_S_MAX,
            ),
            STALE_THRESHOLD_S_MIN,
        )


@dataclass
class ProximityData:
    """Data published by the coordinator to sensor entities."""

    proximity: dict[str, str | int | float | None]
    entities: dict[str, dict[str, str | int | float | bool | None]]


DEFAULT_PROXIMITY_DATA: dict[str, str | int | float | None] = {
    ATTR_DIST_TO: DEFAULT_DIST_TO_ZONE,
    ATTR_DIR_OF_TRAVEL: DEFAULT_DIR_OF_TRAVEL,
    ATTR_NEAREST: DEFAULT_NEAREST,
    ATTR_SPEED: None,
}


# -- Coordinator ----------------------------------------------------------------


class ProximityDataUpdateCoordinator(DataUpdateCoordinator[ProximityData]):
    """Proximity data update coordinator.

    Design goals
    ------------
    * Speed      - weighted average of segment speeds across the position window.
                   Determines whether the entity is stationary.
    * Direction  - dot product of v_move (oldest->newest sample) and v_zone
                   (last position -> zone centre), both in a local equirectangular
                   projection.  Perpendicular movement preserves the last valid
                   direction.  Solves the "orbiting" case cleanly.
    * Decay      - when no new GPS fix arrives, a one-shot timer fires after
                   the usual sample period and injects a synthetic stationary sample,
                   diluting the speed average toward 0.  The timer is cancelled
                   immediately when a real GPS fix is received, and rescheduled
                   after each decay tick as long as any entity still moves.
    """

    config_entry: ProximityConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ProximityConfigEntry) -> None:
        """Initialize the coordinator."""
        conf = {**config_entry.data, **config_entry.options}
        self.ignored_zone_ids: list[str] = conf[CONF_IGNORED_ZONES]
        self.speed_threshold: float = conf.get(
            CONF_SPEED_THRESHOLD, DEFAULT_SPEED_THRESHOLD
        )
        self.tolerance: int = conf[CONF_TOLERANCE]
        self.tracked_entities: list[str] = conf[CONF_TRACKED_ENTITIES]
        self.proximity_zone_id: str = conf[CONF_ZONE]
        self.unit_of_measurement: str = conf.get(
            CONF_UNIT_OF_MEASUREMENT, hass.config.units.length_unit
        )
        self.entity_mapping: dict[str, list[str]] = defaultdict(list)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            # No update_interval: updates are driven exclusively by state-change
            # events and by the decay timer below.
        )

        self.data = ProximityData(dict(DEFAULT_PROXIMITY_DATA), {})
        # Per-entity movement state, keyed by entity_id.
        self._movement: dict[str, EntityMovementState] = {}
        # One-shot timer that fires a decay refresh when GPS goes silent.
        self._decay_unsub: CALLBACK_TYPE | None = None

    # -- Public helpers ---------------------------------------------------------

    @callback
    def async_add_entity_mapping(self, tracked_entity_id: str, entity_id: str) -> None:
        """Add a tracked entity to proximity entity mapping."""
        self.entity_mapping[tracked_entity_id].append(entity_id)

    # -- Decay timer ------------------------------------------------------------

    @callback
    def _cancel_decay_timer(self) -> None:
        """Cancel any pending decay timer."""
        if self._decay_unsub is not None:
            self._decay_unsub()
            self._decay_unsub = None

    @callback
    def _schedule_decay(self) -> None:
        """(Re)schedule a one-shot decay refresh after the usual sample period.

        Called at the end of each update that still reports non-zero speed for
        at least one entity.  Any previously scheduled timer is cancelled first
        so that rapid successive updates do not stack timers.
        """
        self._cancel_decay_timer()

        @callback
        def _decay_callback(_now: datetime) -> None:
            self._decay_unsub = None
            self.hass.async_create_task(
                self.async_refresh(), eager_start=True, name="proximity decay tick"
            )

        # Find the shortest decay interval in all tracked entities
        now = dt_util.utcnow()
        stale_threshold_s: float = STALE_THRESHOLD_S_MAX
        for mov in self._movement.values():
            if len(mov.samples) > 1:
                latest = mov.samples[-1].timestamp
                offset = max((now - latest).total_seconds(), 0)
                stale_threshold_s = min(
                    mov.update_period() - offset,
                    stale_threshold_s,
                )
        stale_threshold_s = max(stale_threshold_s, 0.0)
        self._decay_unsub = async_call_later(
            self.hass, stale_threshold_s, _decay_callback
        )
        _LOGGER.debug("%s: decay timer scheduled in %s", self.name, stale_threshold_s)

    # -- Event handlers ---------------------------------------------------------

    async def async_check_proximity_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle a state-changed event for a tracked entity or the monitored zone.

        Zone changes trigger a distance recalculation only.
        Tracked entity changes additionally record a new position sample.
        """
        data = event.data
        entity_id: str = data["entity_id"]
        new_state = data["new_state"]

        if entity_id not in self.tracked_entities:
            return

        if new_state is not None:
            lat = new_state.attributes.get(ATTR_LATITUDE)
            lon = new_state.attributes.get(ATTR_LONGITUDE)
            if lat is not None and lon is not None:
                # A real GPS fix arrived: cancel the pending decay timer so it
                # does not fire redundantly right after this refresh.
                self._cancel_decay_timer()
                self._add_position_sample(entity_id, float(lat), float(lon))

        await self.async_refresh()

    async def async_check_tracked_entity_change(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Handle entity-registry updates for tracked entities."""
        data = event.data
        if data["action"] == "remove":
            self._create_removed_tracked_entity_issue(data["entity_id"])

        if data["action"] == "update" and "entity_id" in data["changes"]:
            old_tracked_entity_id: str = data["old_entity_id"]
            new_tracked_entity_id: str = data["entity_id"]

            # Migrate movement history to the renamed entity.
            if old_tracked_entity_id in self._movement:
                self._movement[new_tracked_entity_id] = self._movement.pop(
                    old_tracked_entity_id
                )

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_TRACKED_ENTITIES: [
                        tracked_entity
                        for tracked_entity in (
                            *self.tracked_entities,
                            new_tracked_entity_id,
                        )
                        if tracked_entity != old_tracked_entity_id
                    ],
                },
            )

    # -- Shutdown ---------------------------------------------------------------

    async def async_shutdown(self) -> None:
        """Cancel the decay timer and shut down the coordinator."""
        self._cancel_decay_timer()
        await super().async_shutdown()

    # -- Position sample management ---------------------------------------------

    def _add_position_sample(
        self, entity_id: str, latitude: float, longitude: float
    ) -> None:
        """Append a real GPS sample for *entity_id*.

        Lazily initializes the EntityMovementState if needed (e.g. when a state
        change arrives before the first periodic refresh has run).
        """
        if entity_id not in self._movement:
            self._movement[entity_id] = EntityMovementState()

        self._movement[entity_id].samples.append(
            PositionSample(
                timestamp=dt_util.utcnow(),
                latitude=latitude,
                longitude=longitude,
            )
        )

    def _maybe_inject_stale_sample(
        self, mov: EntityMovementState, entity_id: str
    ) -> None:
        """Inject a synthetic stationary sample if GPS has gone silent.

        Each injected sample carries the last known position with the current
        wall-clock time.  After enough ticks the window fills with zero-speed
        segments and the weighted average speed falls below the threshold,
        transitioning the entity to 'stationary'.
        """
        if not mov.samples:
            return
        latest = mov.samples[-1].timestamp
        now = dt_util.utcnow()
        age = (now - latest).total_seconds()
        if age >= mov.update_period():
            last = mov.samples[-1]
            mov.samples.append(
                PositionSample(
                    timestamp=now,
                    latitude=last.latitude,
                    longitude=last.longitude,
                )
            )
            _LOGGER.debug(
                "Injected stale sample for %s (%.0f s since last GPS fix)",
                entity_id,
                age,
            )

    # -- Geometry helpers -------------------------------------------------------

    @staticmethod
    def _to_cartesian(
        ref_lat: float, ref_lon: float, lat: float, lon: float
    ) -> tuple[float, float]:
        """Equirectangular projection centred on (ref_lat, ref_lon) -> metres.

        x grows eastward, y grows northward.
        Accurate enough for the distances (< ~100 km) typical of proximity zones.
        """
        cos_ref = math.cos(math.radians(ref_lat))
        x = math.radians(lon - ref_lon) * cos_ref * _EARTH_RADIUS_M
        y = math.radians(lat - ref_lat) * _EARTH_RADIUS_M
        return x, y

    # -- Movement calculations --------------------------------------------------

    @staticmethod
    def _calc_speed(samples: deque[PositionSample]) -> float | None:
        """Weighted average speed (m/s) over consecutive sample pairs.

        Each segment speed is weighted by the recency of its endpoint:
          w[i] = 1 - age_of_sample[i] / total_period   (higher weight = more recent)
        For better responsiveness, we only check the last 15 minutes of samples.

        Using actual great-circle distance between consecutive positions means
        that slow drifts and GPS jitter both contribute correctly to the average.
        """
        if len(samples) < 2:
            return None

        now = samples[-1].timestamp
        total_period = min(
            (now - samples[0].timestamp).total_seconds(), SPEED_WINDOW_MAX_AGE_S
        )
        if total_period <= 0:
            return None
        total_weight = 0.0
        weighted_speed_sum = 0.0

        for i in range(1, len(samples)):
            dt = (samples[i].timestamp - samples[i - 1].timestamp).total_seconds()
            if dt <= 0:
                continue

            age = (now - samples[i].timestamp).total_seconds()
            if age > SPEED_WINDOW_MAX_AGE_S:
                continue
            weight = 1.0 - age / total_period

            seg_dist = distance(
                samples[i - 1].latitude,
                samples[i - 1].longitude,
                samples[i].latitude,
                samples[i].longitude,
            )
            if seg_dist is None:
                continue

            weighted_speed_sum += weight * (seg_dist / dt)
            total_weight += weight

        # Weight of zero means only old samples, no movement
        return 0.0 if total_weight == 0 else weighted_speed_sum / total_weight

    def _calc_direction(
        self,
        samples: deque[PositionSample],
        zone_lat: float,
        zone_lon: float,
        last_valid_direction: str | None,
    ) -> str | None:
        """Resolve direction using the dot product of v_move and v_zone.

        Both vectors are expressed in a local equirectangular frame centred on
        the newest sample position.

        v_move = pos[-1] - pos[0]
            The cumulative displacement over the window.  Equivalent to the
            vector sum of all consecutive segment vectors (telescoping sum),
            so oscillating motion partially cancels out.

        v_zone = zone_centre - pos[-1]
            Points from the current position toward the zone.

        Decision
        --------
        cos theta = (v_move . v_zone) / (|v_move| . |v_zone|)

          cos theta > +DOT_THRESHOLD_COS  ->  "towards"
          cos theta < -DOT_THRESHOLD_COS  ->  "away_from"
          |cos theta| <=  DOT_THRESHOLD_COS  ->  perpendicular; return last_valid
        """
        if len(samples) < 2:
            return None

        last = samples[-1]
        first = samples[0]

        # Local Cartesian system centred on the newest position.
        ref_lat, ref_lon = last.latitude, last.longitude

        # v_move = last - first.  Since last maps to (0, 0):
        x_first, y_first = self._to_cartesian(
            ref_lat, ref_lon, first.latitude, first.longitude
        )
        vx_move = -x_first
        vy_move = -y_first

        # v_zone = zone_centre - last (last is origin)
        vx_zone, vy_zone = self._to_cartesian(ref_lat, ref_lon, zone_lat, zone_lon)

        mag_move = math.hypot(vx_move, vy_move)
        mag_zone = math.hypot(vx_zone, vy_zone)

        if mag_move < 1.0:
            # Net displacement under 1 m - effectively no directional signal.
            return None

        if mag_zone < 1.0:
            # Entity is essentially at the zone centre.
            return None

        cos_theta = (vx_move * vx_zone + vy_move * vy_zone) / (mag_move * mag_zone)

        if abs(cos_theta) <= DOT_THRESHOLD_COS:
            # Movement is perpendicular to the zone vector (e.g. orbiting).
            return (
                last_valid_direction
                if last_valid_direction in ("towards", "away_from")
                else None
            )

        return "towards" if cos_theta > 0 else "away_from"

    # -- Core update ------------------------------------------------------------

    async def _async_update_data(self) -> ProximityData:
        """Recalculate proximity data for every tracked entity.

        Called on state-change events and on decay timer ticks.  At the end of
        each run, a new decay timer is scheduled if at least one entity still
        reports a non-zero speed (meaning its window has not yet fully decayed).
        """
        zone_state = self.hass.states.get(self.proximity_zone_id)
        if zone_state is None:
            _LOGGER.debug(
                "%s: zone %s not found - returning defaults",
                self.name,
                self.proximity_zone_id,
            )
            return ProximityData(dict(DEFAULT_PROXIMITY_DATA), {})

        zone_lat: float = zone_state.attributes[ATTR_LATITUDE]
        zone_lon: float = zone_state.attributes[ATTR_LONGITUDE]
        zone_radius: float = zone_state.attributes["radius"]

        # Build a fresh dict - never mutate self.data in place.
        entities_data: dict[str, dict[str, str | int | float | bool | None]] = {}

        for entity_id in self.tracked_entities:
            if (tracked_entity_state := self.hass.states.get(entity_id)) is None:
                if entity_id in self._movement:
                    _LOGGER.debug(
                        "%s: %s does not exist -> remove", self.name, entity_id
                    )
                    del self._movement[entity_id]
                continue

            # Lazily initialize movement state and seed with current position.
            if entity_id not in self._movement:
                self._movement[entity_id] = EntityMovementState()
                lat = tracked_entity_state.attributes.get(ATTR_LATITUDE)
                lon = tracked_entity_state.attributes.get(ATTR_LONGITUDE)
                if lat is not None and lon is not None:
                    # _add_position_sample checks entity presence so call after
                    # the state above has been stored.
                    self._add_position_sample(entity_id, float(lat), float(lon))

            mov = self._movement[entity_id]

            # -- Decay injection -----------------------------------------------
            self._maybe_inject_stale_sample(mov, entity_id)

            # -- Distance (coordinate-based only) ------------------------------
            lat = tracked_entity_state.attributes.get(ATTR_LATITUDE)
            lon = tracked_entity_state.attributes.get(ATTR_LONGITUDE)

            dist_to_zone: int | None
            if lat is None or lon is None:
                _LOGGER.debug(
                    "%s: %s has no coordinates -> distance=None",
                    self.name,
                    entity_id,
                )
                dist_to_zone = None
            else:
                raw_dist = distance(zone_lat, zone_lon, float(lat), float(lon))
                if raw_dist is None:
                    dist_to_zone = mov.distance_to_zone
                else:
                    dist_to_zone = (
                        0 if zone_radius >= raw_dist else round(raw_dist - zone_radius)
                    )
            last_distance = mov.distance_to_zone
            mov.distance_to_zone = dist_to_zone

            # -- Unknown -------------------------------------------------------
            if dist_to_zone is None:
                mov.direction = None
                mov.speed = None
            elif dist_to_zone == 0:
                # -- Arrived ---------------------------------------------------
                mov.direction = "arrived"
                mov.speed = 0.0
            else:
                # -- Speed -----------------------------------------------------
                mov.speed = self._calc_speed(mov.samples)

                # -- Direction -------------------------------------------------
                direction: str | None
                if mov.speed is None:
                    direction = None
                elif mov.speed < self.speed_threshold:
                    direction = "stationary"
                    mov.speed = 0.0
                else:
                    direction = self._calc_direction(
                        mov.samples,
                        zone_lat,
                        zone_lon,
                        mov.direction,
                    )
                    if direction is None and last_distance is not None:
                        movement = dist_to_zone - last_distance
                        if movement < -self.tolerance:
                            direction = "towards"
                        elif movement > self.tolerance:
                            direction = "away_from"
                        else:
                            direction = mov.direction

                mov.direction = direction

            # -- Ignored-zone flag ---------------------------------------------
            mov.in_ignored_zone = (
                f"{ZONE_DOMAIN}.{tracked_entity_state.state.lower()}"
                in self.ignored_zone_ids
            )

            entities_data[entity_id] = {
                ATTR_NAME: tracked_entity_state.name,
                ATTR_DIST_TO: mov.distance_to_zone,
                ATTR_DIR_OF_TRAVEL: mov.direction,
                ATTR_SPEED: round(mov.speed, 2) if mov.speed is not None else None,
                ATTR_IN_IGNORED_ZONE: mov.in_ignored_zone,
            }

            _LOGGER.debug(
                "%s: %-40s  dist=%-8s  speed=%5.2f m/s  dir=%s",
                self.name,
                entity_id,
                mov.distance_to_zone,
                mov.speed if mov.speed is not None else 0.0,
                mov.direction,
            )

        # -- Schedule next decay tick if any entity still moves ----------------
        needs_decay = any(
            (self._movement[eid].speed or 0) > 0
            for eid in self.tracked_entities
            if eid in self._movement
        )
        if needs_decay:
            self._schedule_decay()
        else:
            # All entities are stationary/arrived: no further decay needed.
            self._cancel_decay_timer()

        # -- Proximity sensor (nearest non-ignored entity) ---------------
        proximity_data: dict[str, str | int | float | None] = dict(
            DEFAULT_PROXIMITY_DATA
        )

        for entity_data in entities_data.values():
            if entity_data[ATTR_IN_IGNORED_ZONE] or entity_data[ATTR_DIST_TO] is None:
                continue

            current_dist = cast(int, entity_data[ATTR_DIST_TO])

            if isinstance(proximity_data[ATTR_DIST_TO], str):
                # First eligible entity found (sentinel is a str).
                proximity_data = {
                    ATTR_DIST_TO: current_dist,
                    ATTR_DIR_OF_TRAVEL: entity_data[ATTR_DIR_OF_TRAVEL],
                    ATTR_NEAREST: str(entity_data[ATTR_NAME]),
                    ATTR_SPEED: entity_data[ATTR_SPEED],
                }
                continue

            nearest_dist = cast(int, proximity_data[ATTR_DIST_TO])

            if nearest_dist > current_dist:
                proximity_data = {
                    ATTR_DIST_TO: current_dist,
                    ATTR_DIR_OF_TRAVEL: entity_data[ATTR_DIR_OF_TRAVEL],
                    ATTR_NEAREST: str(entity_data[ATTR_NAME]),
                    ATTR_SPEED: entity_data[ATTR_SPEED],
                }
            elif nearest_dist == current_dist:
                # Tie: combine names.
                proximity_data[ATTR_NEAREST] = (
                    f"{proximity_data[ATTR_NEAREST]}, {entity_data[ATTR_NAME]!s}"
                )

        return ProximityData(proximity_data, entities_data)

    # -- Issue reporting --------------------------------------------------------

    def _create_removed_tracked_entity_issue(self, entity_id: str) -> None:
        """Create a repair issue when a tracked entity is removed from the registry."""
        async_create_issue(
            self.hass,
            DOMAIN,
            f"tracked_entity_removed_{entity_id}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            translation_key="tracked_entity_removed",
            translation_placeholders={"entity_id": entity_id, "name": self.name},
        )
