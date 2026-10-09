"""The OpenEVSE integration."""

import asyncio
import contextlib
import logging

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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
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


def _parse_voltage_state(state: State | None) -> int | None:
    """Parse voltage sensor state and convert to Volts if necessary."""
    if not state or state.state in (None, "unavailable", "unknown", ""):
        return None
    try:
        val = float(state.state)
    except ValueError, TypeError:
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

    return round(val)


def _parse_range_state(state: State | None) -> int | None:
    """Parse vehicle range sensor state and convert to kilometers if necessary."""
    if not state or state.state in (None, "unavailable", "unknown", ""):
        return None
    try:
        val = float(state.state)
    except ValueError, TypeError:
        return None

    unit = state.attributes.get("unit_of_measurement")
    if (
        unit
        and unit != UnitOfLength.KILOMETERS
        and unit in DistanceConverter.VALID_UNITS
    ):
        with contextlib.suppress(Exception):
            val = DistanceConverter.convert(val, unit, UnitOfLength.KILOMETERS)

    return round(val)


def _parse_int_state(state: State | None) -> int | None:
    """Parse sensor state to integer."""
    if not state or state.state in (None, "unavailable", "unknown", ""):
        return None
    try:
        return round(float(state.state))
    except ValueError, TypeError:
        return None


def _parse_eta_state(state: State | None) -> int | None:
    """Parse vehicle ETA sensor state in seconds, converting datetime or duration units if needed."""
    if not state or state.state in (None, "unavailable", "unknown", ""):
        return None
    try:
        val = float(state.state)
        unit = state.attributes.get("unit_of_measurement")
        if (
            unit
            and unit != UnitOfTime.SECONDS
            and unit in DurationConverter.VALID_UNITS
        ):
            with contextlib.suppress(Exception):
                val = DurationConverter.convert(val, unit, UnitOfTime.SECONDS)
        return round(val)
    except ValueError, TypeError:
        pass

    if dt := dt_util.parse_datetime(state.state):
        now = dt_util.utcnow()
        remaining = round((dt - now).total_seconds())
        return max(0, remaining)

    return None


async def _handle_sensor_update(
    hass: HomeAssistant,
    entry: OpenEVSEConfigEntry,
    changed_entity: str,
) -> None:
    """Track updates to configured sensor entities and push data to OpenEVSE."""
    coordinator = entry.runtime_data
    charger = coordinator.charger
    options = entry.options

    try:
        if changed_entity == options.get(CONF_GRID):
            grid = _parse_power_state(hass.states.get(changed_entity))
            invert = options.get(CONF_INVERT_GRID, False)
            await charger.self_production(grid=grid, solar=None, invert=invert)

        if changed_entity == options.get(CONF_SOLAR):
            solar = _parse_power_state(hass.states.get(changed_entity))
            await charger.self_production(grid=None, solar=solar, invert=False)

        if changed_entity == options.get(CONF_VOLTAGE):
            voltage = _parse_voltage_state(hass.states.get(changed_entity))
            if voltage is not None:
                await charger.grid_voltage(voltage=voltage)

        if changed_entity == options.get(CONF_SHAPER):
            power = _parse_power_state(hass.states.get(changed_entity))
            if power is not None:
                await charger.set_shaper_live_pwr(power=power)

        if changed_entity in (
            options.get(CONF_VEHICLE_SOC),
            options.get(CONF_VEHICLE_RANGE),
            options.get(CONF_VEHICLE_ETA),
        ):
            soc_sensor = options.get(CONF_VEHICLE_SOC)
            range_sensor = options.get(CONF_VEHICLE_RANGE)
            eta_sensor = options.get(CONF_VEHICLE_ETA)

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

        if changed_entity in (
            options.get(CONF_HOME_BATTERY_SOC),
            options.get(CONF_HOME_BATTERY_POWER),
        ):
            hb_soc_sensor = options.get(CONF_HOME_BATTERY_SOC)
            hb_power_sensor = options.get(CONF_HOME_BATTERY_POWER)

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
        _LOGGER.debug(
            "Authentication failed while pushing %s update: %s", changed_entity, err
        )
        entry.async_start_reauth(hass)
    except UnsupportedFeature:
        _LOGGER.debug(
            "Pushing %s data is unsupported by this OpenEVSE firmware", changed_entity
        )
    except (
        TimeoutError,
        ServerTimeoutError,
        ContentTypeError,
        ParseJSONError,
        UnknownError,
        RuntimeError,
        ValueError,
        OSError,
    ) as err:
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
                entities_to_process = list(pending_entities)
                pending_entities.clear()
                for entity_id in entities_to_process:
                    await _handle_sensor_update(hass, entry, entity_id)

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

        # Replay current states for configured sensors on startup
        for sensor_id in tracked_sensors:
            if hass.states.get(sensor_id) is not None:
                _schedule_update(sensor_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenEVSEConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
