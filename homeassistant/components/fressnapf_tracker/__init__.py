"""The Fressnapf Tracker integration."""

import logging

from fressnapftracker import (
    ApiClient,
    AuthClient,
    Device,
    FressnapfTrackerAuthenticationError,
    FressnapfTrackerError,
    FressnapfTrackerInvalidTrackerResponseError,
    Tracker,
)

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_USER_ID, DOMAIN
from .coordinator import (
    FressnapfTrackerConfigEntry,
    FressnapfTrackerDataUpdateCoordinator,
)
from .util import hashed_serial_number

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


def invalid_tracker_issue_id(entry_id: str, serialnumber: str) -> str:
    """Return the repair issue ID for an invalid tracker.

    The ID contains the config entry ID because a tracker can be shared
    between accounts. The serial number is hashed because issue IDs are
    appended to diagnostics downloads without redaction. The placeholders
    of a non persistent issue are not part of the download.
    """
    return f"invalid_fressnapf_tracker_{entry_id}_{hashed_serial_number(serialnumber)}"


def _delete_stale_invalid_tracker_issues(
    hass: HomeAssistant, entry: FressnapfTrackerConfigEntry, current_issue_ids: set[str]
) -> None:
    """Delete invalid tracker issues of this entry that no longer apply.

    This also removes issues created by earlier versions, which had the serial
    number in their ID, even if the tracker has recovered or was removed since.
    """
    prefix = f"invalid_fressnapf_tracker_{entry.entry_id}_"
    for domain, issue_id in list(ir.async_get(hass).issues):
        if (
            domain == DOMAIN
            and issue_id.startswith(prefix)
            and issue_id not in current_issue_ids
        ):
            ir.async_delete_issue(hass, DOMAIN, issue_id)


async def _get_valid_tracker(
    hass: HomeAssistant, entry: FressnapfTrackerConfigEntry, device: Device
) -> Tracker | None:
    """Test if the tracker returns valid data and return it.

    Malformed data might indicate the tracker is broken or
    hasn't been properly registered with the app.
    """
    client = ApiClient(
        serial_number=device.serialnumber,
        device_token=device.token,
        client=get_async_client(hass),
    )
    try:
        return await client.get_tracker()
    except FressnapfTrackerInvalidTrackerResponseError:
        _LOGGER.warning(
            "Tracker with serialnumber %s is invalid. Consider removing it via the App",
            device.serialnumber,
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            invalid_tracker_issue_id(entry.entry_id, device.serialnumber),
            config_entry_id=entry.entry_id,
            issue_domain=DOMAIN,
            learn_more_url="https://www.home-assistant.io/integrations/fressnapf_tracker/",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="invalid_fressnapf_tracker",
            translation_placeholders={
                "tracker_id": device.serialnumber,
            },
        )
        return None
    except FressnapfTrackerError as err:
        raise ConfigEntryNotReady(err) from err


async def async_setup_entry(
    hass: HomeAssistant, entry: FressnapfTrackerConfigEntry
) -> None:
    """Set up Fressnapf Tracker from a config entry."""
    auth_client = AuthClient(client=get_async_client(hass))
    try:
        devices = await auth_client.get_devices(
            user_id=entry.data[CONF_USER_ID],
            user_access_token=entry.data[CONF_ACCESS_TOKEN],
        )
    except FressnapfTrackerAuthenticationError as exception:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from exception

    coordinators: list[FressnapfTrackerDataUpdateCoordinator] = []
    invalid_issue_ids: set[str] = set()
    for device in devices:
        tracker = await _get_valid_tracker(hass, entry, device)
        if tracker is None:
            invalid_issue_ids.add(
                invalid_tracker_issue_id(entry.entry_id, device.serialnumber)
            )
            continue
        coordinator = FressnapfTrackerDataUpdateCoordinator(
            hass,
            entry,
            device,
            initial_data=tracker,
        )
        coordinators.append(coordinator)

    entry.runtime_data = coordinators

    _delete_stale_invalid_tracker_issues(hass, entry, invalid_issue_ids)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: FressnapfTrackerConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
