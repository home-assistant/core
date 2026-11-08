"""The OpenEVSE integration."""

import asyncio
import contextlib
import logging
import math

from aiohttp import ContentTypeError, ServerTimeoutError
from openevsehttp.__main__ import OpenEVSE
from openevsehttp.exceptions import (
    AuthenticationError,
    MissingSerial,
    ParseJSONError,
    UnknownError,
    UnsupportedFeature,
)

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    DurationConverter,
    ElectricPotentialConverter,
    PowerConverter,
)

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
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

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
        if not math.isfinite(val):
            return None
    except ValueError, TypeError, OverflowError:
        return None

    unit = state.attributes.get("unit_of_measurement")
    if unit and unit != UnitOfPower.WATT:
        with contextlib.suppress(Exception):
            val = PowerConverter.convert(val, unit, UnitOfPower.WATT)

    if not math.isfinite(val):
        return None

    try:
        return round(val)
    except OverflowError:
        return None


def _parse_voltage_state(state: State | None) -> int | None:
    """Parse voltage sensor state and convert to Volts if necessary."""
    if not state or state.state in (None, "unavailable", "unknown", ""):
        return None
    try:
        val = float(state.state)
        if not math.isfinite(val):
            return None
    except ValueError, TypeError, OverflowError:
        return None

    unit = state.attributes.get("unit_of_measurement")
    if (
        unit
        and unit != UnitOfElectricPotential.VOLT
        and unit in ElectricPotentialConverter.VALID_UNITS
    ):
        with contextlib.suppress(Exception):
            val = ElectricPotentialConverter.convert(
                val, unit, UnitOfElectricPotential.VOLT
            )

    if not math.isfinite(val):
        return None

    try:
        return round(val)
    except OverflowError:
        return None


def _parse_range_state(state: State | None) -> int | None:
    """Parse vehicle range sensor state and convert to kilometers if necessary."""
    if not state or state.state in (None, "unavailable", "unknown", ""):
        return None
    try:
        val = float(state.state)
        if not math.isfinite(val):
            return None
    except ValueError, TypeError, OverflowError:
        return None

    unit = state.attributes.get("unit_of_measurement")
    if (
        unit
        and unit != UnitOfLength.KILOMETERS
        and unit in DistanceConverter.VALID_UNITS
    ):
        with contextlib.suppress(Exception):
            val = DistanceConverter.convert(val, unit, UnitOfLength.KILOMETERS)

    if not math.isfinite(val):
        return None

    try:
        return round(val)
    except OverflowError:
        return None


def _parse_int_state(state: State | None) -> int | None:
    """Parse sensor state to integer."""
    if not state or state.state in (None, "unavailable", "unknown", ""):
        return None
    try:
        val = float(state.state)
        if not math.isfinite(val):
            return None
        return round(val)
    except ValueError, TypeError, OverflowError:
        return None


def _parse_eta_state(state: State | None) -> int | None:
    """Parse vehicle ETA sensor state in seconds, converting datetime or duration units if needed."""
    if not state or state.state in (None, "unavailable", "unknown", ""):
        return None
    try:
        val = float(state.state)
        if not math.isfinite(val):
            return None
        unit = state.attributes.get("unit_of_measurement")
        if (
            unit
            and unit != UnitOfTime.SECONDS
            and unit in DurationConverter.VALID_UNITS
        ):
            with contextlib.suppress(Exception):
                val = DurationConverter.convert(val, unit, UnitOfTime.SECONDS)
        if not math.isfinite(val):
            return None
        return round(val)
    except ValueError, TypeError, OverflowError:
        pass

    if dt := dt_util.parse_datetime(state.state):
        now = dt_util.utcnow()
        remaining = round((dt - now).total_seconds())
        return max(0, remaining)

    return None


async def _handle_sensor_updates(
    hass: HomeAssistant,
    entry: OpenEVSEConfigEntry,
    entities_to_process: set[str],
) -> None:
    """Track updates to configured sensor entities and push data to OpenEVSE."""
    coordinator = entry.runtime_data
    charger = coordinator.charger
    options = entry.options

    try:
        grid_sensor = options.get(CONF_GRID)
        if grid_sensor and grid_sensor in entities_to_process:
            grid = _parse_power_state(hass.states.get(grid_sensor))
            invert = options.get(CONF_INVERT_GRID, False)
            await charger.self_production(grid=grid, solar=None, invert=invert)

        solar_sensor = options.get(CONF_SOLAR)
        if solar_sensor and solar_sensor in entities_to_process:
            solar = _parse_power_state(hass.states.get(solar_sensor))
            await charger.self_production(grid=None, solar=solar, invert=False)

        voltage_sensor = options.get(CONF_VOLTAGE)
        if voltage_sensor and voltage_sensor in entities_to_process:
            voltage = _parse_voltage_state(hass.states.get(voltage_sensor))
            if voltage is not None:
                await charger.grid_voltage(voltage=voltage)

        shaper_sensor = options.get(CONF_SHAPER)
        if shaper_sensor and shaper_sensor in entities_to_process:
            power = _parse_power_state(hass.states.get(shaper_sensor))
            if power is not None:
                await charger.set_shaper_live_pwr(power=power)

        soc_sensor = options.get(CONF_VEHICLE_SOC)
        range_sensor = options.get(CONF_VEHICLE_RANGE)
        eta_sensor = options.get(CONF_VEHICLE_ETA)
        vehicle_sensors = {s for s in (soc_sensor, range_sensor, eta_sensor) if s}
        if vehicle_sensors & entities_to_process:
            soc = _parse_int_state(hass.states.get(soc_sensor)) if soc_sensor else None
            vrange = (
                _parse_range_state(hass.states.get(range_sensor))
                if range_sensor
                else None
            )
            eta = _parse_eta_state(hass.states.get(eta_sensor)) if eta_sensor else None

            await charger.soc(
                battery_level=soc,
                battery_range=vrange,
                time_to_full=eta,
            )

        hb_soc_sensor = options.get(CONF_HOME_BATTERY_SOC)
        hb_power_sensor = options.get(CONF_HOME_BATTERY_POWER)
        hb_sensors = {s for s in (hb_soc_sensor, hb_power_sensor) if s}
        if hb_sensors & entities_to_process:
            hb_soc = (
                _parse_int_state(hass.states.get(hb_soc_sensor))
                if hb_soc_sensor
                else None
            )
            hb_power = (
                _parse_power_state(hass.states.get(hb_power_sensor))
                if hb_power_sensor
                else None
            )

            await charger.home_battery(soc=hb_soc, power=hb_power)

    except AuthenticationError as err:
        _LOGGER.debug("Authentication failed while pushing sensor update: %s", err)
        entry.async_start_reauth(hass)
    except UnsupportedFeature:
        _LOGGER.debug("Pushing sensor data is unsupported by this OpenEVSE firmware")
    except (
        TimeoutError,
        ServerTimeoutError,
        ContentTypeError,
        ParseJSONError,
        UnknownError,
        RuntimeError,
        ValueError,
        OverflowError,
        OSError,
    ) as err:
        _LOGGER.debug("Failed to push sensor update to OpenEVSE charger: %s", err)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OpenEVSE component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OpenEVSEConfigEntry) -> None:
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
    tracked_sensors = list(
        {
            sensor_id
            for field in SENSOR_FIELDS
            if (sensor_id := entry.options.get(field))
        }
    )
    if tracked_sensors:
        pending_entities: set[str] = set()
        work_available = asyncio.Event()

        async def _push_worker() -> None:
            """Process pending sensor entity updates sequentially and coalesced."""
            while True:
                await work_available.wait()
                work_available.clear()
                entities_to_process = set(pending_entities)
                pending_entities.clear()
                await _handle_sensor_updates(hass, entry, entities_to_process)

        entry.async_create_background_task(
            hass,
            _push_worker(),
            "openevse_push_worker",
        )

        @callback
        def _schedule_update(entity_id: str) -> None:
            pending_entities.add(entity_id)
            work_available.set()

        @callback
        def _on_sensor_state_change(event: Event[EventStateChangedData]) -> None:
            _schedule_update(event.data["entity_id"])

        entry.async_on_unload(
            async_track_state_change_event(
                hass, tracked_sensors, _on_sensor_state_change
            )
        )

        @callback
        def _on_entity_registry_update(
            event: Event[er.EventEntityRegistryUpdatedData],
        ) -> None:
            data = event.data
            if data["action"] != "update" or "entity_id" not in data["changes"]:
                return

            old_entity_id = data["changes"]["entity_id"]
            new_entity_id = data["entity_id"]

            updated_options = {
                field: new_entity_id if current_id == old_entity_id else current_id
                for field in SENSOR_FIELDS
                if (current_id := entry.options.get(field))
            }
            if updated_options:
                hass.config_entries.async_update_entry(
                    entry,
                    options={**entry.options, **updated_options},
                )
                hass.config_entries.async_schedule_reload(entry.entry_id)

        entry.async_on_unload(
            async_track_entity_registry_updated_event(
                hass, tracked_sensors, _on_entity_registry_update
            )
        )

        # Replay current states for configured sensors on startup
        for sensor_id in tracked_sensors:
            if hass.states.get(sensor_id) is not None:
                _schedule_update(sensor_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: OpenEVSEConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
