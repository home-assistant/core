"""The Tesla Powerwall integration."""
from __future__ import annotations

import contextlib
from datetime import timedelta
import logging

import requests
from tesla_powerwall import (
    AccessDeniedError,
    APIError,
    MissingAttributeError,
    Powerwall,
    PowerwallError,
    PowerwallUnreachableError,
)

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.network import is_ip_address

from .const import (
    DOMAIN,
    POWERWALL_API_CHANGED,
    POWERWALL_COORDINATOR,
    POWERWALL_HTTP_SESSION,
    UPDATE_INTERVAL,
)
from .models import PowerwallBaseInfo, PowerwallData, PowerwallRuntimeData

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

API_CHANGED_ERROR_BODY = (
    "It seems like your powerwall uses an unsupported version. "
    "Please update the software of your powerwall or if it is "
    "already the newest consider reporting this issue.\nSee logs for more information"
)
API_CHANGED_TITLE = "Unknown powerwall software version"


class PowerwallDataManager:
    """Class to manager powerwall data and relogin on failure."""

    def __init__(
        self,
        hass: HomeAssistant,
        power_wall: Powerwall,
        ip_address: str,
        password: str | None,
        runtime_data: PowerwallRuntimeData,
    ) -> None:
        """Init the data manager."""
        self.hass = hass
        self.ip_address = ip_address
        self.password = password
        self.runtime_data = runtime_data
        self.power_wall = power_wall

    @property
    def api_changed(self) -> int:
        """Return true if the api has changed out from under us."""
        return self.runtime_data[POWERWALL_API_CHANGED]

    def _recreate_powerwall_login(self) -> None:
        """Recreate the login on auth failure."""
        if self.power_wall.is_authenticated():
            self.power_wall.logout()
        self.power_wall.login(self.password or "")

    async def async_update_data(self) -> PowerwallData:
        """Fetch data from API endpoint."""
        # Check if we had an error before
        _LOGGER.debug("Checking if update failed")
        if self.api_changed:
            raise UpdateFailed("The powerwall api has changed")
        return await self.hass.async_add_executor_job(self._update_data)

    def _update_data(self) -> PowerwallData:
        """Fetch data from API endpoint."""
        _LOGGER.debug("Updating data")
        for attempt in range(2):
            try:
                if attempt == 1:
                    self._recreate_powerwall_login()
                data = _fetch_powerwall_data(self.power_wall)
            except PowerwallUnreachableError as err:
                raise UpdateFailed("Unable to fetch data from powerwall") from err
            except MissingAttributeError as err:
                _LOGGER.error("The powerwall api has changed: %s", str(err))
                # The error might include some important information about what exactly changed.
                persistent_notification.create(
                    self.hass, API_CHANGED_ERROR_BODY, API_CHANGED_TITLE
                )
                self.runtime_data[POWERWALL_API_CHANGED] = True
                raise UpdateFailed("The powerwall api has changed") from err
            except AccessDeniedError as err:
                if attempt == 1:
                    # failed to authenticate => the credentials must be wrong
                    raise ConfigEntryAuthFailed from err
                if self.password is None:
                    raise ConfigEntryAuthFailed from err
                _LOGGER.debug("Access denied, trying to reauthenticate")
                # there is still an attempt left to authenticate, so we continue in the loop
            except APIError as err:
                raise UpdateFailed(f"Updated failed due to {err}, will retry") from err
            else:
                return data
        raise RuntimeError("unreachable")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tesla Powerwall from a config entry."""
    http_session = requests.Session()
    ip_address = entry.data[CONF_IP_ADDRESS]

    password = entry.data.get(CONF_PASSWORD)
    power_wall = Powerwall(ip_address, http_session=http_session)
    try:
        base_info = await hass.async_add_executor_job(
            _login_and_fetch_base_info, power_wall, ip_address, password
        )
    except PowerwallUnreachableError as err:
        http_session.close()
        raise ConfigEntryNotReady from err
    except MissingAttributeError as err:
        http_session.close()
        # The error might include some important information about what exactly changed.
        _LOGGER.error("The powerwall api has changed: %s", str(err))
        persistent_notification.async_create(
            hass, API_CHANGED_ERROR_BODY, API_CHANGED_TITLE
        )
        return False
    except AccessDeniedError as err:
        _LOGGER.debug("Authentication failed", exc_info=err)
        http_session.close()
        raise ConfigEntryAuthFailed from err
    except APIError as err:
        http_session.close()
        raise ConfigEntryNotReady from err

    gateway_din = base_info.gateway_din
    if gateway_din and entry.unique_id is not None and is_ip_address(entry.unique_id):
        hass.config_entries.async_update_entry(entry, unique_id=gateway_din)

    runtime_data = PowerwallRuntimeData(
        api_changed=False,
        base_info=base_info,
        http_session=http_session,
        coordinator=None,
    )

    manager = PowerwallDataManager(hass, power_wall, ip_address, password, runtime_data)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Powerwall site",
        update_method=manager.async_update_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    runtime_data[POWERWALL_COORDINATOR] = coordinator

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _login_and_fetch_base_info(
    power_wall: Powerwall, host: str, password: str
) -> PowerwallBaseInfo:
    """Login to the powerwall and fetch the base info."""
    if password is not None:
        power_wall.login(password)
    return call_base_info(power_wall, host)


def call_base_info(power_wall: Powerwall, host: str) -> PowerwallBaseInfo:
    """Return PowerwallBaseInfo for the device."""
    # Make sure the serial numbers always have the same order
    gateway_din = None
    with contextlib.suppress(AssertionError, PowerwallError):
        gateway_din = power_wall.get_gateway_din().upper()
    return PowerwallBaseInfo(
        gateway_din=gateway_din,
        site_info=power_wall.get_site_info(),
        status=power_wall.get_status(),
        device_type=power_wall.get_device_type(),
        serial_numbers=sorted(power_wall.get_serial_numbers()),
        url=f"https://{host}",
    )


def _fetch_powerwall_data(power_wall: Powerwall) -> PowerwallData:
    """Process and update powerwall data."""
    try:
        backup_reserve = power_wall.get_backup_reserve_percentage()
    except MissingAttributeError:
        backup_reserve = None

    return PowerwallData(
        charge=power_wall.get_charge(),
        site_master=power_wall.get_sitemaster(),
        meters=power_wall.get_meters(),
        grid_services_active=power_wall.is_grid_services_active(),
        grid_status=power_wall.get_grid_status(),
        backup_reserve=backup_reserve,
    )


@callback
def async_last_update_was_successful(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Return True if the last update was successful."""
    return bool(
        (domain_data := hass.data.get(DOMAIN))
        and (entry_data := domain_data.get(entry.entry_id))
        and (coordinator := entry_data.get(POWERWALL_COORDINATOR))
        and coordinator.last_update_success
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data[DOMAIN][entry.entry_id][POWERWALL_HTTP_SESSION].close()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
