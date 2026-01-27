"""The Fressnapf Tracker integration."""

import logging

from fressnapftracker import (
    ApiClient,
    AuthClient,
    Device,
    FressnapfTrackerAuthenticationError,
    FressnapfTrackerError,
    FressnapfTrackerInvalidTrackerResponseError,
)

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_USER_ID, DOMAIN
from .coordinator import (
    FressnapfTrackerConfigEntry,
    FressnapfTrackerDataUpdateCoordinator,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def _tracker_is_valid(hass: HomeAssistant, device: Device) -> bool:
    """Test if the tracker returns valid data.

    Malformed data might indicate the tracker is broken or hasn't been properly registered with the app.
    """
    client = ApiClient(
        serial_number=device.serialnumber,
        device_token=device.token,
        client=get_async_client(hass),
    )
    try:
        await client.get_tracker()
    except FressnapfTrackerInvalidTrackerResponseError:
        _LOGGER.warning(
            "Tracker with serialnumber %s is invalid. Consider removing it via the App",
            device.serialnumber,
        )
        async_create_issue(
            hass,
            DOMAIN,
            f"invalid_fressnapf_tracker_{device.serialnumber}",
            issue_domain=DOMAIN,
            learn_more_url="https://www.home-assistant.io/integrations/fressnapf_tracker/",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="invalid_fressnapf_tracker",
            translation_placeholders={
                "tracker_id": device.serialnumber,
            },
        )
        return False
    except FressnapfTrackerError as err:
        raise ConfigEntryNotReady(err) from err
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: FressnapfTrackerConfigEntry
) -> bool:
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
    for device in devices:
        if not await _tracker_is_valid(hass, device):
            continue
        coordinator = FressnapfTrackerDataUpdateCoordinator(
            hass,
            entry,
            device,
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators.append(coordinator)

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: FressnapfTrackerConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
