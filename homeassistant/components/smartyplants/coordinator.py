"""Polling coordinator for SmartyPlants, with webhook push support."""

from datetime import datetime
import logging
from typing import Any, override

from pysmartyplants import SmartyPlantsAuthError, SmartyPlantsClient, SmartyPlantsError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLANT_KEY_PREFIX,
    STALE_AFTER,
    STATUS_NO_PLANT,
    STATUS_NO_SENSOR,
    STATUS_OFFLINE,
    STATUS_OK,
    STATUS_OUTDATED,
    STATUS_WAITING,
)

_LOGGER = logging.getLogger(__name__)

type SmartyPlantsConfigEntry = ConfigEntry[SmartyPlantsCoordinator]


def last_reported(sensor: dict[str, Any]) -> datetime | None:
    """Return when this sensor last reported, as an aware UTC datetime."""
    raw = sensor.get("lastDataReceived")
    if not raw:
        return None

    # A pushed timestamp can be any JSON type, and anything that is not a
    # string or datetime would raise on .tzinfo below.
    if isinstance(raw, str):
        parsed = dt_util.parse_datetime(raw)
    elif isinstance(raw, datetime):
        parsed = raw
    else:
        return None
    if parsed is None:
        return None

    # The backend sends UTC. Treat a naive timestamp as UTC rather than local,
    # otherwise a non-UTC Home Assistant would misjudge staleness by its offset.
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt_util.UTC)
    return dt_util.as_utc(parsed)


def is_stale(sensor: dict[str, Any]) -> bool:
    """Return True when the last reading is too old to be trusted.

    A sensor may still be considered reachable by the backend while its last
    readings have aged past STALE_AFTER. Those values no longer describe the
    plant, so we stop presenting them as current.
    """
    reported = last_reported(sensor)
    if reported is None:
        return True

    return dt_util.utcnow() - reported > STALE_AFTER


def _dict_or(value: Any, fallback: Any) -> Any:
    """Return value when it is a usable mapping, else keep what we had."""
    return value if isinstance(value, dict) else fallback


def is_usable(sensor: dict[str, Any]) -> bool:
    """Return True when readings are both fresh and from an online sensor."""
    if not sensor.get("isPaired", True):
        return False
    return bool(sensor.get("isOnline")) and not is_stale(sensor)


def setup_status(sensor: dict[str, Any]) -> str:
    """Describe what, if anything, the user still needs to do.

    Ordered most-blocking first: an unpaired plant or sensor cannot produce
    readings at all, so that is reported ahead of connectivity problems.
    """
    if sensor.get("isPlantOnly"):
        return STATUS_NO_SENSOR
    if not sensor.get("plant"):
        return STATUS_NO_PLANT
    if not sensor.get("readings"):
        return STATUS_WAITING
    if not sensor.get("isOnline"):
        return STATUS_OFFLINE
    if is_stale(sensor):
        return STATUS_OUTDATED
    return STATUS_OK


class SmartyPlantsCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Fetches all sensors on one schedule and indexes them by sensor id."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SmartyPlantsConfigEntry,
        client: SmartyPlantsClient,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        # Bumped by every applied push. A poll that started before a push
        # must not overwrite it with the older snapshot it fetched.
        self._push_revision = 0

    @override
    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Poll the backend and key the sensors by id."""
        revision = self._push_revision

        try:
            sensors = await self.client.async_get_sensors()
            plants = await self.client.async_get_plants()
        except SmartyPlantsAuthError as err:
            # Reported as an update failure rather than starting a re-auth
            # flow, which this integration does not offer yet.
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except SmartyPlantsError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err

        if revision != self._push_revision and self.data is not None:
            # A push landed while this poll was in flight, so it already holds
            # newer readings than the response we just received. The next poll
            # picks up anything this one would have added.
            return self.data

        data = {sensor["id"]: sensor for sensor in sensors if sensor.get("id")}

        # Plants with no sensor get their own device so the user can see the
        # plant exists and knows to attach a sensor to it.
        for plant in plants:
            if plant.get("sensor") or not plant.get("id"):
                continue
            data[f"{PLANT_KEY_PREFIX}{plant['id']}"] = {
                "id": plant["id"],
                "identifier": None,
                "name": plant.get("name"),
                "isOnline": False,
                "isPaired": False,
                "isPlantOnly": True,
                "batteryPercentage": None,
                "lastDataReceived": None,
                "plant": {
                    "id": plant["id"],
                    "name": plant.get("name"),
                    "imageUrl": plant.get("imageUrl"),
                    "environment": plant.get("environment"),
                    "species": plant.get("species"),
                    "commonNames": plant.get("commonNames") or [],
                },
                "health": plant.get("health"),
                "readings": None,
            }

        # A sensor with no plant is equally unpaired: it cannot be scored
        # against a species, so its readings are not presented either.
        for sensor in sensors:
            if sensor.get("id") and not sensor.get("plant"):
                data[sensor["id"]]["isPaired"] = False

        # The poll is authoritative for the full set, so anything missing here
        # was deleted in the app. Webhook pushes carry a single sensor and are
        # deliberately not used to infer removal.
        self._async_purge_removed_devices(data)
        self._async_sync_pairing_issues(data)

        return data

    @callback
    def async_sync_devices(self) -> None:
        """Keep device names and areas in step with the app.

        A plant can be renamed, moved to another environment, or unassigned
        from its sensor between polls. Called after platform setup and on every
        subsequent update, since devices only exist once entities are added.
        """
        entry = self.config_entry
        if entry is None:
            return

        data = self.data or {}

        registry = dr.async_get(self.hass)

        for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
            sensor_id = next(
                (ident[1] for ident in device.identifiers if ident[0] == DOMAIN), None
            )
            if sensor_id is None or (sensor := data.get(sensor_id)) is None:
                continue

            updates: dict[str, Any] = {}

            plant = sensor.get("plant") or {}
            name = plant.get("name") or sensor.get("name") or sensor.get("identifier")
            if name and name != device.name:
                updates["name"] = name

            # Only place the device when the user has not chosen an area
            # themselves; their choice always wins over the app's environment.
            if device.area_id is None and (environment := plant.get("environment")):
                area = ar.async_get(self.hass).async_get_or_create(environment)
                updates["area_id"] = area.id

            if updates:
                _LOGGER.debug("Syncing device %s: %s", device.id, updates)
                registry.async_update_device(device.id, **updates)

    @callback
    def _async_purge_removed_devices(self, data: dict[str, dict[str, Any]]) -> None:
        """Drop devices for sensors that no longer exist in the account."""
        entry = self.config_entry
        if entry is None:
            return

        registry = dr.async_get(self.hass)
        current = {(DOMAIN, sensor_id) for sensor_id in data}

        for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
            if device.identifiers & current:
                continue

            _LOGGER.debug("Removing device for deleted sensor: %s", device.name)
            # Removing the device takes its entities with it.
            registry.async_remove_device(device.id)

    @callback
    def async_remove_sensor(self, sensor_id: str) -> None:
        """Drop a sensor that was deleted in the app.

        Optional fast path for the sensor_removed push event. The poll reaches
        the same result on its own, so nothing breaks if the backend never
        sends it.
        """
        if sensor_id not in (self.data or {}):
            return

        data = dict(self.data)
        del data[sensor_id]

        self._async_purge_removed_devices(data)
        self._async_sync_pairing_issues(data)
        self._push_revision += 1
        self.async_set_updated_data(data)

    @callback
    def _async_sync_pairing_issues(self, data: dict[str, dict[str, Any]]) -> None:
        """Raise a repair for anything the user still needs to pair.

        A plant with no sensor, or a sensor with no plant, cannot produce
        readings until the user finishes setting it up in the app. Issues are
        reconciled on every poll so they clear themselves once resolved.
        """
        entry = self.config_entry
        if entry is None:
            return

        expected: set[str] = set()

        for key, sensor in data.items():
            status = setup_status(sensor)
            if status == STATUS_NO_SENSOR:
                issue_id = f"no_sensor_{key}"
                translation_key = "plant_without_sensor"
            elif status == STATUS_NO_PLANT:
                issue_id = f"no_plant_{key}"
                translation_key = "sensor_without_plant"
            else:
                continue

            expected.add(issue_id)
            name = (sensor.get("plant") or {}).get("name") or sensor.get("name")
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=translation_key,
                translation_placeholders={"name": name or "Unknown"},
            )

        # Clear issues for pairings the user has since completed.
        for issue in list(ir.async_get(self.hass).issues.values()):
            if (
                issue.domain == DOMAIN
                and issue.issue_id.startswith(("no_sensor_", "no_plant_"))
                and issue.issue_id not in expected
            ):
                ir.async_delete_issue(self.hass, DOMAIN, issue.issue_id)

    @callback
    def async_apply_webhook_payload(self, payload: dict[str, Any]) -> None:
        """Merge a pushed sensor_update into the cached data.

        The webhook payload is flatter than the REST response and omits the
        species details, so it is merged onto the existing entry rather than
        replacing it.
        """
        pushed = payload.get("sensor") or {}
        sensor_id = pushed.get("id")
        if not sensor_id:
            _LOGGER.debug("Ignoring webhook payload without a sensor id")
            return

        data = dict(self.data or {})
        merged = dict(data.get(sensor_id, {}))
        existing_plant = merged.get("plant") or {}

        # A push that omits its timestamp must not blank the one we already
        # have, or every entity would immediately read as stale.
        timestamp = payload.get("timestamp") or merged.get("lastDataReceived")

        # Only carry a plant when one is actually known. Fabricating a dict of
        # None values would make an unpaired sensor look paired.
        plant_id = pushed.get("plantId") or existing_plant.get("id")
        plant_name = pushed.get("plantName") or existing_plant.get("name")
        plant = (
            {**existing_plant, "id": plant_id, "name": plant_name}
            if plant_id or plant_name
            else None
        )

        merged.update(
            {
                "id": sensor_id,
                "identifier": pushed.get("identifier", merged.get("identifier")),
                "name": pushed.get("name", merged.get("name")),
                "isOnline": pushed.get("isOnline", merged.get("isOnline", True)),
                "batteryPercentage": pushed.get(
                    "batteryPercentage", merged.get("batteryPercentage")
                ),
                "lastDataReceived": timestamp,
                # Shapes are checked before they land: a malformed push must
                # not poison the cache the entities read from.
                "health": _dict_or(payload.get("health"), merged.get("health")),
                "readings": _dict_or(payload.get("readings"), merged.get("readings")),
                "plant": plant,
                "isPaired": plant is not None,
            }
        )

        data[sensor_id] = merged
        self._push_revision += 1
        self.async_set_updated_data(data)
