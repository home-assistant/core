"""The Tesla Powerwall integration."""

from __future__ import annotations

import logging

import pypowerwall
from pypowerwall.local.exceptions import LoginError as PowerwallLoginError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import POWERWALL_COORDINATOR
from .coordinator import (
    MeterData,
    PowerwallBaseInfo,
    PowerwallConfigEntry,
    PowerwallData,
    PowerwallRuntimeData,
    PowerwallUpdateCoordinator,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


def _parse_meter(data: dict) -> MeterData:
    """Parse meter data from API response."""
    return MeterData(
        instant_power=data.get("instant_power", 0),
        energy_exported=data.get("energy_exported", 0),
        energy_imported=data.get("energy_imported", 0),
        instant_average_voltage=data.get("instant_average_voltage", 0),
        instant_total_current=data.get("instant_total_current", 0),
        frequency=data.get("frequency", 0),
    )


class PowerwallDataManager:
    """Class to manage powerwall data and handle updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        power_wall: pypowerwall.Powerwall,
        entry: PowerwallConfigEntry,
        base_info: PowerwallBaseInfo,
    ) -> None:
        """Initialize the data manager."""
        self.hass = hass
        self.power_wall = power_wall
        self.entry = entry
        self.base_info = base_info

    async def async_update_data(self) -> PowerwallData:
        """Fetch data from the Powerwall."""
        try:
            return await self.hass.async_add_executor_job(self._fetch_data)
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

    def _fetch_data(self) -> PowerwallData:
        """Fetch data from the Powerwall (sync)."""
        # Get meter data
        meters = self.power_wall.poll("/api/meters/aggregates")
        if meters is None:
            raise UpdateFailed("Failed to fetch meter data")

        grid_data = self.power_wall.poll("/api/system_status/grid_status") or {}

        # Get battery level
        charge = self.power_wall.level()
        if charge is None:
            raise UpdateFailed("Failed to fetch battery level")

        # Get grid status
        grid_status = self.power_wall.grid_status()
        if grid_status is None:
            raise UpdateFailed("Failed to fetch grid status")

        # Get grid services active
        grid_services_active = grid_data.get("grid_services_active", False)

        # Parse meter data
        site_data = meters.get("site", {})
        battery_data = meters.get("battery", {})
        load_data = meters.get("load", {})
        solar_data = meters.get("solar")

        return PowerwallData(
            charge=charge,
            grid_status=grid_status,
            grid_services_active=grid_services_active,
            site=_parse_meter(site_data),
            battery=_parse_meter(battery_data),
            load=_parse_meter(load_data),
            solar=_parse_meter(solar_data) if solar_data else None,
        )


def _fetch_base_info(power_wall: pypowerwall.Powerwall, host: str) -> PowerwallBaseInfo:
    """Fetch base info, detecting PW2 vs PW3."""
    # Try PW2-specific endpoints
    site_name = power_wall.site_name()
    version = power_wall.version()

    if site_name is None and version is None:
        # PW3: Limited API — /api/status returns 404, so no DIN/serial.
        # Use IP as unique_id.
        return PowerwallBaseInfo(
            unique_id=host,
            site_name=None,
            version=None,
            device_type="Powerwall 3",
            url=f"https://{host}",
            is_powerwall3=True,
        )

    # PW2: Full API available — prefer gateway DIN as unique_id
    gateway_din = power_wall.din()
    return PowerwallBaseInfo(
        unique_id=gateway_din or host,
        site_name=site_name,
        version=version,
        device_type="Powerwall 2",
        url=f"https://{host}",
        is_powerwall3=False,
    )


async def async_setup_entry(hass: HomeAssistant, entry: PowerwallConfigEntry) -> bool:
    """Set up Tesla Powerwall from a config entry."""
    ip_address: str = entry.data[CONF_IP_ADDRESS]
    password: str | None = entry.data.get(CONF_PASSWORD)

    try:
        # Create pypowerwall instance (sync library, run in executor)
        power_wall = await hass.async_add_executor_job(
            _create_powerwall, ip_address, password or ""
        )
    except PowerwallLoginError as err:
        raise ConfigEntryAuthFailed("Invalid Powerwall credentials") from err
    except Exception as err:
        raise ConfigEntryNotReady(f"Cannot connect to {ip_address}") from err

    # Test connection by getting battery level
    try:
        level = await hass.async_add_executor_job(power_wall.level)
    except PowerwallLoginError as err:
        raise ConfigEntryAuthFailed("Invalid Powerwall credentials") from err
    except Exception as err:
        raise ConfigEntryNotReady(f"Cannot connect to {ip_address}") from err

    if level is None:
        raise ConfigEntryNotReady("Unable to get battery level")

    # Fetch base info
    base_info = await hass.async_add_executor_job(
        _fetch_base_info, power_wall, ip_address
    )

    # Create runtime data
    runtime_data: PowerwallRuntimeData = {
        "coordinator": None,
        "api_instance": power_wall,
        "base_info": base_info,
    }

    # Create data manager and coordinator
    manager = PowerwallDataManager(hass, power_wall, entry, base_info)
    coordinator = PowerwallUpdateCoordinator(hass, entry, manager)

    await coordinator.async_config_entry_first_refresh()

    runtime_data[POWERWALL_COORDINATOR] = coordinator
    entry.runtime_data = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _create_powerwall(ip_address: str, password: str) -> pypowerwall.Powerwall:
    """Create a pypowerwall instance."""
    return pypowerwall.Powerwall(
        host=ip_address,
        password=password,
        email="homeassistant@local",  # Required but unused for local auth
        timezone="UTC",
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
