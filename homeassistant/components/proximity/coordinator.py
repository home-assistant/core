"""Data update coordinator for the Proximity integration."""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
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
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
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
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# -- Earth geometry -------------------------------------------------------------
_EARTH_RADIUS_M: float = 6_371_000.0

# -- Movement window tuning -----------------------------------------------------

POSITION_WINDOW_SIZE: int = 8
"""Number of position samples retained per entity (sliding window)."""

DOT_THRESHOLD_COS: float = 0.5
"""cos(60°): minimum |cosine| of the angle between v_move and v_zone for the
   direction to be resolved as 'towards' or 'away_from'.  When the angle exceeds
   60° (movement roughly perpendicular to the zone vector) the last valid
   direction is preserved instead."""

STALE_THRESHOLD_S_MIN: float = 300.0
"""Minimum seconds after which a stationary synthetic sample is injected.  This causes
   speed to decay toward 0 and the entity to become 'stationary' when no real
   GPS updates arrive (decay mechanism)."""

STALE_THRESHOLD_S_MAX: float = 900.0
"""Maximum seconds after which a stationary synthetic sample is injected.  This causes
   speed to decay toward 0 and the entity to become 'stationary' when no real
   GPS updates arrive (decay mechanism)."""

UPDATE_INTERVAL: timedelta = timedelta(seconds=30)
"""Periodic tick that drives the decay mechanism.  Each tick may inject one
   synthetic sample per entity and recalculates movement data."""

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


@dataclass
class ProximityData:
    """Data published by the coordinator to sensor entities."""

    proximity: dict[str, str | int | float | None]
    entities: dict[str, dict[str, str | int | float | None]]


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
    * Decay      - periodic ticks inject a synthetic sample at the last known
                   position, diluting the speed average toward 0 when no real
                   GPS updates arrive.
    """

    config_entry: ProximityConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ProximityConfigEntry) -> None:
        """Initialise the coordinator."""
        self.ignored_zone_ids: list[str] = config_entry.data[CONF_IGNORED_ZONES]
        self.speed_threshold: float = config_entry.data.get(CONF_SPEED_THRESHOLD, 0.5)
        self.tolerance: int = config_entry.data[CONF_TOLERANCE]
        self.tracked_entities: list[str] = config_entry.data[CONF_TRACKED_ENTITIES]
        self.proximity_zone_id: str = config_entry.data[CONF_ZONE]
        self.unit_of_measurement: str = config_entry.data.get(
            CONF_UNIT_OF_MEASUREMENT, hass.config.units.length_unit
        )
        self.entity_mapping: dict[str, list[str]] = defaultdict(list)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            # Periodic ticks drive the decay mechanism even when GPS is silent.
            update_interval=UPDATE_INTERVAL,
        )

        self.data = ProximityData(dict(DEFAULT_PROXIMITY_DATA), {})
        # Per-entity movement state, keyed by entity_id.
        self._movement: dict[str, EntityMovementState] = {}

    # -- Public helpers ---------------------------------------------------------

    @callback
    def async_add_entity_mapping(self, tracked_entity_id: str, entity_id: str) -> None:
        """Add a tracked entity to proximity entity mapping."""
        self.entity_mapping[tracked_entity_id].append(entity_id)

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

        if entity_id == self.proximity_zone_id:
            # Zone geometry changed; distances need to be recalculated but no
            # new position sample is produced.
            await self.async_refresh()
            return

        if entity_id not in self.tracked_entities:
            return

        if new_state is not None:
            lat = new_state.attributes.get(ATTR_LATITUDE)
            lon = new_state.attributes.get(ATTR_LONGITUDE)
            if lat is not None and lon is not None:
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

    # -- Position sample management ---------------------------------------------

    def _add_position_sample(
        self, entity_id: str, latitude: float, longitude: float
    ) -> None:
        """Append a real GPS sample for *entity_id*.

        Lazily initialises the EntityMovementState if needed (e.g. when a state
        change arrives before the first periodic refresh has run).
        """
        if entity_id not in self._movement:
            self._movement[entity_id] = EntityMovementState()

        self._movement[entity_id].samples.append(
            PositionSample(
                timestamp=datetime.now(UTC),
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
        # Allow for some jitter beyond the threshold.
        stale_threshold_s = (
            1.1 * (latest - mov.samples[0].timestamp).total_seconds() / len(mov.samples)
            if len(mov.samples) > 1
            else STALE_THRESHOLD_S_MAX
        )
        stale_threshold_s = min(
            max(stale_threshold_s, STALE_THRESHOLD_S_MIN), STALE_THRESHOLD_S_MAX
        )
        now = datetime.now(UTC)
        age = (now - latest).total_seconds()
        if age >= stale_threshold_s:
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
    def _calc_speed(samples: deque[PositionSample], tolerance: float) -> float | None:
        """Weighted average speed (m/s) over consecutive sample pairs.

        Each segment speed is weighted by the recency of its endpoint:
          w[i] = 1 - age_of_sample[i] / total_period   (higher weight = more recent)

        Using actual great-circle distance between consecutive positions means
        that slow drifts and GPS jitter both contribute correctly to the average.
        """
        if len(samples) < 2:
            return None

        now = samples[-1].timestamp
        total_period = max(
            (now - samples[0].timestamp).total_seconds(), STALE_THRESHOLD_S_MAX
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
            if age > STALE_THRESHOLD_S_MAX:
                break
            weight = 1.0 - age / total_period

            seg_dist = distance(
                samples[i - 1].latitude,
                samples[i - 1].longitude,
                samples[i].latitude,
                samples[i].longitude,
            )
            if seg_dist is None:
                continue
            if seg_dist < tolerance:
                # Ignore minor movements within the configured tolerance.
                seg_dist = 0.0

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
        sample_list = list(samples)
        if len(sample_list) < 2:
            return None

        last = sample_list[-1]
        first = sample_list[0]

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
            return last_valid_direction

        return "towards" if cos_theta > 0 else "away_from"

    # -- Core update ------------------------------------------------------------

    async def _async_update_data(self) -> ProximityData:
        """Recalculate proximity data for every tracked entity.

        Called both on state-change events and on the periodic UPDATE_INTERVAL
        tick that drives the speed-decay mechanism.

        Key correctness properties
        --------------------------
        * Distance is always derived from raw GPS coordinates, never from
          entity.state zone membership, preventing false zeros from stale
          secondary trackers.
        * A deep copy of entities_data is built from scratch each run; there is
          no partial mutation of self.data before a potential exception, so
          self.data stays fully consistent after each successful update.
        * self._movement is the sole persistent store between runs and is only
          updated when the full calculation completes successfully.
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
        entities_data: dict[str, dict[str, str | int | float | None]] = {}

        for entity_id in self.tracked_entities:
            if (tracked_entity_state := self.hass.states.get(entity_id)) is None:
                if entities_data.pop(entity_id, None) is not None:
                    _LOGGER.debug(
                        "%s: %s does not exist -> remove", self.name, entity_id
                    )
                continue

            # Lazily initialise movement state and seed with current position.
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
            if tracked_entity_state.state.lower() == self.proximity_zone_id.lower():
                _LOGGER.debug(
                    "%s: %s in zone -> direction_of_travel=arrived",
                    self.name,
                    entity_id,
                )
                dist_to_zone = 0
            elif lat is None or lon is None:
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

            # -- Arrived -------------------------------------------------------
            if dist_to_zone == 0:
                mov.direction = "arrived"
                mov.speed = 0
                mov.samples.clear()
            else:
                # -- Speed -----------------------------------------------------
                mov.speed = self._calc_speed(mov.samples, self.tolerance)

                # -- Direction -------------------------------------------------
                direction: str | None
                if mov.speed is None or dist_to_zone is None:
                    direction = None
                elif mov.speed < self.speed_threshold:
                    direction = "stationary"
                    mov.speed = 0
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
