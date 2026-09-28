"""The tractive integration."""

import asyncio
import logging
from typing import TYPE_CHECKING

import aiotractive
from aiotractive import PetStatus, TrackerStatus
from aiotractive.models import (
    merge_tracker_status,
    tracker_status_from_rest,
    update_pet_from_health_overview,
)

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT_ID, DOMAIN
from .coordinator import (
    Trackables,
    TractiveConfigEntry,
    TractiveCoordinator,
    TractiveData,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: TractiveConfigEntry) -> bool:
    """Set up tractive from a config entry."""
    data = entry.data

    client = aiotractive.Tractive(
        data[CONF_EMAIL],
        data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
        client_id=CLIENT_ID,
    )
    try:
        creds = await client.authenticate()
    except aiotractive.exceptions.UnauthorizedError as error:
        await client.close()
        raise ConfigEntryAuthFailed from error
    except aiotractive.exceptions.TractiveError as error:
        await client.close()
        raise ConfigEntryNotReady from error

    if TYPE_CHECKING:
        assert creds is not None

    coordinator = TractiveCoordinator(hass, client, creds["user_id"], entry)

    trackables = []
    try:
        for obj in await client.trackable_objects():
            await asyncio.sleep(2)
            trackables.append(await _generate_trackables(client, obj))
    except aiotractive.exceptions.TractiveError as error:
        await client.close()
        raise ConfigEntryNotReady from error
    except ConfigEntryNotReady:
        await client.close()
        raise

    filtered_trackables = [item for item in trackables if item]

    _populate_initial_status(coordinator.client, filtered_trackables)

    entry.runtime_data = TractiveData(coordinator, filtered_trackables)

    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_start()

    # Register the tracker devices so entities on the pet devices can resolve
    # their via_device link at construction time.
    device_registry = dr.async_get(hass)
    for item in filtered_trackables:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            configuration_url="https://my.tractive.com/",
            identifiers={(DOMAIN, item.tracker_details["_id"])},
            translation_key="tracker",
            translation_placeholders={"id": item.tracker_details["_id"]},
            manufacturer="Tractive GmbH",
            sw_version=item.tracker_details["fw_version"],
            model_id=item.tracker_details["model_number"],
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    coordinator.async_set_updated_data(None)

    async def cancel_listen_task(_: Event) -> None:
        await coordinator.async_shutdown()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cancel_listen_task)
    )
    entry.async_on_unload(coordinator.async_shutdown)

    entity_reg = er.async_get(hass)
    for item in filtered_trackables:
        for key in ("activity_label", "calories", "sleep_label"):
            if entity_id := entity_reg.async_get_entity_id(
                SENSOR_DOMAIN, DOMAIN, f"{item.trackable['_id']}_{key}"
            ):
                entity_reg.async_remove(entity_id)

    return True


def _populate_initial_status(
    client: aiotractive.Tractive, trackables: list[Trackables]
) -> None:
    """Populate the initial status from fetched data."""
    for item in trackables:
        merge_tracker_status(
            client.status.trackers.setdefault(
                item.tracker_details["_id"], TrackerStatus()
            ),
            tracker_status_from_rest(
                item.tracker_details, item.hw_info, item.pos_report
            ),
        )
        pet_status = client.status.pets.setdefault(item.trackable["_id"], PetStatus())
        if item.health_overview:
            update_pet_from_health_overview(pet_status, item.health_overview)


async def _generate_trackables(
    client: aiotractive.Tractive,
    trackable: aiotractive.trackable_object.TrackableObject,
) -> Trackables | None:
    """Generate trackables."""
    trackable_data = await trackable.details()

    if not trackable_data.get("device_id"):
        return None

    if "details" not in trackable_data:
        _LOGGER.warning(
            "Tracker %s has no details and will be"
            " skipped. This happens for shared trackers",
            trackable_data["device_id"],
        )
        return None

    tracker = client.tracker(trackable_data["device_id"])
    trackable_pet = client.trackable_object(trackable_data["_id"])

    tracker_details = await tracker.details()
    hw_info = await tracker.hw_info()
    pos_report = await tracker.pos_report()
    health_overview = await trackable_pet.health_overview()

    if not tracker_details.get("_id"):
        raise ConfigEntryNotReady(
            "Tractive API returns incomplete data"
            f" for tracker {trackable_data['device_id']}",
        )

    return Trackables(
        tracker, trackable_data, tracker_details, hw_info, pos_report, health_overview
    )


async def async_unload_entry(hass: HomeAssistant, entry: TractiveConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
