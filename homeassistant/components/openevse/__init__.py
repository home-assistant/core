"""The OpenEVSE integration."""

import contextlib
import logging

from openevsehttp.__main__ import OpenEVSE
from openevsehttp.exceptions import (
    AuthenticationError,
    MissingSerial,
    UnsupportedFeature,
)

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
    UnitOfPower,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_conversion import PowerConverter

from .const import (
    CONF_GRID,
    CONF_HOME_BATTERY_POWER,
    CONF_HOME_BATTERY_SOC,
    CONF_INVERT_GRID,
    CONF_SHAPER,
    CONF_SOLAR,
    CONF_VEHICLE_ETA,
    CONF_VEHICLE_RANGE,
    CONF_VEHICLE_SOC,
    CONF_VOLTAGE,
    DOMAIN,
    SENSOR_FIELDS,
)
from .coordinator import OpenEVSEConfigEntry, OpenEVSEDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


def _parse_power_state(state: State | None) -> int | None:
    """Parse power sensor state and convert to Watts if necessary."""
    if not state or state.state in (None, "unavailable", "unknown", ""):
        return None
    try:
        val = float(state.state)
    except ValueError, TypeError:
        return None

    unit = state.attributes.get("unit_of_measurement")
    if unit and unit != UnitOfPower.WATT:
        with contextlib.suppress(Exception):
            val = PowerConverter.convert(val, unit, UnitOfPower.WATT)

    return round(val)


async def _handle_sensor_state_change(
    hass: HomeAssistant,
    entry: OpenEVSEConfigEntry,
    event: Event[EventStateChangedData],
) -> None:
    """Track state changes to configured sensor entities and push data to OpenEVSE."""
    coordinator = entry.runtime_data
    charger = coordinator.charger
    options = entry.options
    changed_entity = event.data["entity_id"]

    try:
        if changed_entity == options.get(CONF_GRID):
            grid = _parse_power_state(hass.states.get(changed_entity))
            invert = options.get(CONF_INVERT_GRID, False)
            await charger.self_production(grid=grid, solar=None, invert=invert)

        elif changed_entity == options.get(CONF_SOLAR):
            solar = _parse_power_state(hass.states.get(changed_entity))
            await charger.self_production(grid=None, solar=solar, invert=False)

        elif changed_entity == options.get(CONF_VOLTAGE):
            state = hass.states.get(changed_entity)
            voltage: int | None = None
            if state and state.state not in (None, "unavailable", "unknown", ""):
                try:
                    voltage = round(float(state.state))
                except ValueError, TypeError:
                    voltage = None
            await charger.grid_voltage(voltage=voltage)

        elif changed_entity == options.get(CONF_SHAPER):
            power = _parse_power_state(hass.states.get(changed_entity))
            if power is not None:
                await charger.set_shaper_live_pwr(power=power)

        elif changed_entity == options.get(CONF_VEHICLE_SOC):
            state = hass.states.get(changed_entity)
            soc: int | None = None
            if state and state.state not in (None, "unavailable", "unknown", ""):
                try:
                    soc = round(float(state.state))
                except ValueError, TypeError:
                    soc = None
            await charger.soc(battery_level=soc)

        elif changed_entity == options.get(CONF_VEHICLE_RANGE):
            state = hass.states.get(changed_entity)
            vrange: int | None = None
            if state and state.state not in (None, "unavailable", "unknown", ""):
                try:
                    vrange = round(float(state.state))
                except ValueError, TypeError:
                    vrange = None
            await charger.soc(battery_range=vrange)

        elif changed_entity == options.get(CONF_VEHICLE_ETA):
            state = hass.states.get(changed_entity)
            eta: int | None = None
            if state and state.state not in (None, "unavailable", "unknown", ""):
                try:
                    eta = round(float(state.state))
                except ValueError, TypeError:
                    eta = None
            await charger.soc(time_to_full=eta)

        elif changed_entity == options.get(CONF_HOME_BATTERY_SOC):
            state = hass.states.get(changed_entity)
            hb_soc: int | None = None
            if state and state.state not in (None, "unavailable", "unknown", ""):
                try:
                    hb_soc = round(float(state.state))
                except ValueError, TypeError:
                    hb_soc = None
            await charger.home_battery(soc=hb_soc)

        elif changed_entity == options.get(CONF_HOME_BATTERY_POWER):
            hb_power = _parse_power_state(hass.states.get(changed_entity))
            await charger.home_battery(power=hb_power)

    except UnsupportedFeature:
        _LOGGER.debug(
            "Pushing %s data is unsupported by this OpenEVSE firmware", changed_entity
        )
    except (TimeoutError, OSError) as err:
        _LOGGER.debug(
            "Failed to push %s update to OpenEVSE charger: %s", changed_entity, err
        )


async def async_setup_entry(hass: HomeAssistant, entry: OpenEVSEConfigEntry) -> bool:
    """Set up OpenEVSE from a config entry."""
    charger = OpenEVSE(
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        session=async_get_clientsession(hass),
    )

    try:
        await charger.test_and_get()
    except TimeoutError as ex:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
        ) from ex
    except AuthenticationError as ex:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_error",
        ) from ex
    except MissingSerial:
        pass

    coordinator = OpenEVSEDataUpdateCoordinator(hass, entry, charger)
    await coordinator.async_config_entry_first_refresh()

    # Start websocket listener for push updates
    await coordinator.async_start_websocket()

    entry.runtime_data = coordinator

    # Register websocket cleanup on unload
    entry.async_on_unload(coordinator.async_stop_websocket)

    # Track sensor entities configured in options flow
    tracked_sensors = [
        sensor_id for field in SENSOR_FIELDS if (sensor_id := entry.options.get(field))
    ]
    if tracked_sensors:

        @callback
        def _on_sensor_state_change(event: Event[EventStateChangedData]) -> None:
            hass.async_create_task(_handle_sensor_state_change(hass, entry, event))

        entry.async_on_unload(
            async_track_state_change_event(
                hass, tracked_sensors, _on_sensor_state_change
            )
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenEVSEConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
