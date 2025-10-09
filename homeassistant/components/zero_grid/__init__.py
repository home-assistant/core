"""The ZeroGrid integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .config import Config, ControllableLoadConfig
from .const import DOMAIN

# from .sensor import (
#     AvailableAmpsSensor,
#     EnableLoadControlSwitch,
#     LoadControlAmpsSensor,
# )
from .helpers import parse_entity_domain
from .state import ControllableLoadPlanState, ControllableLoadState, PlanState, State

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH]

CONFIG = Config()
STATE = State()
PLAN = PlanState()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Main entry point on startup."""
    domain_config = config[DOMAIN]
    parse_config(domain_config)
    initialise_state(hass)
    subscribe_to_entity_changes(hass)

    # load_platform(hass, "sensor", DOMAIN, domain_config, config)
    # load_platform(hass, "switch", DOMAIN, domain_config, config)

    return True


# async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Set up entities from a config entry."""
#     # _LOGGER.debug("async_setup_entry")

#     await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

#     return True
#     # domain_config = entry
#     # parse_config(domain_config)
#     # initialise_state(hass)
#     # subscribe_to_entity_changes(hass)

#     # async_add_entities(
#     #     [EnableLoadControlSwitch(), AvailableAmpsSensor(), LoadControlAmpsSensor()]
#     # )


# async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Unload a config entry."""
#     return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def parse_config(domain_config):
    """Parses the config and sets appropriates variables."""
    _LOGGER.debug(domain_config)

    CONFIG.max_house_load_amps = domain_config.get("max_house_load_amps")
    CONFIG.hysteresis_amps = domain_config.get("hysteresis_amps", 2)
    CONFIG.recalculate_interval_seconds = domain_config.get(
        "recalculate_interval_seconds", 10
    )
    CONFIG.house_consumption_amps_entity = domain_config.get(
        "house_consumption_amps_entity"
    )
    CONFIG.mains_voltage_entity = domain_config.get("mains_voltage_entity")

    CONFIG.allow_grid_import_entity = domain_config.get(
        "allow_grid_import_entity", None
    )
    CONFIG.allow_grid_import = CONFIG.allow_grid_import_entity is not None

    CONFIG.solar_generation_kw_entity = domain_config.get(
        "solar_generation_kw_entity", None
    )
    CONFIG.allow_solar_consumption = CONFIG.solar_generation_kw_entity is not None

    # Reactive power management settings
    CONFIG.variance_detection_threshold = domain_config.get(
        "variance_detection_threshold", 1.0
    )
    CONFIG.variance_detection_delay_seconds = domain_config.get(
        "variance_detection_delay_seconds", 30
    )
    CONFIG.enable_reactive_reallocation = domain_config.get(
        "enable_reactive_reallocation", True
    )

    control_options = domain_config.get("controllable_loads", [])
    for priority, control in enumerate(control_options):
        control_config = ControllableLoadConfig()
        control_config.name = control.get("name")
        control_config.priority = priority
        control_config.max_controllable_load_amps = control.get(
            "max_controllable_load_amps"
        )
        control_config.min_controllable_load_amps = control.get(
            "min_controllable_load_amps"
        )
        control_config.min_toggle_interval_seconds = control.get(
            "min_toggle_interval_seconds", None
        )
        control_config.min_throttle_interval_seconds = control.get(
            "min_throttle_interval_seconds", None
        )
        control_config.load_amps_entity = control.get("load_amps_entity")
        control_config.switch_entity = control.get("switch_entity")
        control_config.throttle_amps_entity = control.get("throttle_amps_entity", None)
        control_config.can_throttle = control_config.throttle_amps_entity is not None
        CONFIG.controllable_loads[control_config.name] = control_config

    _LOGGER.debug("Config successful: %s", CONFIG)


def initialise_state(hass: HomeAssistant):
    """Initialises the state of the integration."""
    if CONFIG.house_consumption_amps_entity is not None:
        state = hass.states.get(CONFIG.house_consumption_amps_entity)
        if state is not None:
            STATE.house_consumption_amps = float(state.state)

    if CONFIG.mains_voltage_entity is not None:
        state = hass.states.get(CONFIG.mains_voltage_entity)
        if state is not None:
            STATE.mains_voltage = float(state.state)

    if CONFIG.solar_generation_kw_entity is not None:
        state = hass.states.get(CONFIG.solar_generation_kw_entity)
        if state is not None:
            STATE.solar_generation_kw = float(state.state)
    else:
        STATE.solar_generation_kw = 0.0

    if CONFIG.allow_grid_import_entity is not None:
        state = hass.states.get(CONFIG.allow_grid_import_entity)
        if state is not None:
            STATE.allow_grid_import = state.state.lower() == "on"

    # match to controllable loads
    for load_name in CONFIG.controllable_loads:  # pylint: disable=consider-using-dict-items
        config = CONFIG.controllable_loads[load_name]
        load_state = ControllableLoadState()

        switch_state = hass.states.get(config.switch_entity)
        if switch_state is not None:
            load_state.is_on = switch_state.state.lower() == "on"

        load_amps_state = hass.states.get(config.load_amps_entity)
        if load_amps_state is not None:
            load_state.current_load_amps = float(load_amps_state.state)

        STATE.controllable_loads[load_name] = load_state
        PLAN.controllable_loads[load_name] = ControllableLoadPlanState()

    _LOGGER.debug("Initialised state: %s", STATE)


def subscribe_to_entity_changes(hass: HomeAssistant):
    """Subscribes to required entity changes."""
    entity_ids: list[str] = [
        CONFIG.house_consumption_amps_entity,
        CONFIG.mains_voltage_entity,
    ]
    if CONFIG.allow_grid_import_entity is not None:
        entity_ids.append(CONFIG.allow_grid_import_entity)
    if CONFIG.solar_generation_kw_entity is not None:
        entity_ids.append(CONFIG.solar_generation_kw_entity)

    for control in CONFIG.controllable_loads.values():
        entity_ids.append(control.load_amps_entity)
        if control.switch_entity is not None:
            entity_ids.append(control.switch_entity)

    async def state_automation_listener(event: Event[EventStateChangedData]) -> None:
        if event.event_type != "state_changed":
            return

        # Update state based on entity changes
        entity_id = event.data["entity_id"]
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        _LOGGER.debug("Entity changed: %s : %s", entity_id, new_state.state)

        if entity_id == CONFIG.house_consumption_amps_entity:
            if new_state is not None:
                STATE.house_consumption_amps = float(new_state.state)
            else:
                _LOGGER.error(
                    "House consumption entity is unavailable, cutting all load for safety"
                )
                await safety_abort(hass)
                return

        elif entity_id == CONFIG.mains_voltage_entity:
            if new_state is not None:
                STATE.mains_voltage = float(new_state.state)
            else:
                _LOGGER.error(
                    "Mains voltage entity is unavailable, cutting all load for safety"
                )
                await safety_abort(hass)
                return

        elif entity_id == CONFIG.solar_generation_kw_entity:
            if new_state is not None:
                STATE.solar_generation_kw = float(new_state.state)
            else:
                STATE.solar_generation_kw = 0.0
                _LOGGER.warning(
                    "Solar generation entity is unavailable, assuming zero generation"
                )
                return

        elif entity_id == CONFIG.allow_grid_import_entity:
            if new_state is not None:
                STATE.allow_grid_import = new_state.state.lower() == "on"

        else:
            STATE.load_control_consumption_amps = 0.0

            # match to controllable loads
            for control in CONFIG.controllable_loads.values():
                if entity_id == control.switch_entity:
                    if new_state is not None:
                        STATE.controllable_loads[control.name].is_on = (
                            new_state.state.lower() == "on"
                        )
                    else:
                        STATE.controllable_loads[
                            control.name
                        ].is_on = True  # Assume on if unavailable

                if entity_id == control.load_amps_entity:
                    if new_state is not None:
                        STATE.controllable_loads[
                            control.name
                        ].current_load_amps = float(new_state.state)
                    else:
                        STATE.controllable_loads[control.name].current_load_amps = 0.0
                STATE.load_control_consumption_amps += STATE.controllable_loads[
                    control.name
                ].current_load_amps

        await recalculate_load_control(hass)

        # Check for consumption variance and potentially trigger reallocation
        if CONFIG.enable_reactive_reallocation:
            await check_consumption_variance_and_reallocate(hass)

    async def state_time_listener(now: datetime) -> None:
        _LOGGER.debug("Time listener fired")
        await recalculate_load_control(hass)

        # Check for consumption variance and potentially trigger reallocation
        if CONFIG.enable_reactive_reallocation:
            await check_consumption_variance_and_reallocate(hass)

    _LOGGER.debug("Subscribing... %s", entity_ids)
    async_track_state_change_event(hass, entity_ids, state_automation_listener)

    interval = timedelta(seconds=CONFIG.recalculate_interval_seconds)
    async_track_time_interval(hass, state_time_listener, interval)


@bind_hass
async def check_consumption_variance_and_reallocate(hass: HomeAssistant):
    """Check if loads are consuming less than expected and trigger reallocation."""
    if not CONFIG.enable_reactive_reallocation:
        return

    now = datetime.now()
    total_unused_power = 0.0
    loads_with_unused_power = []

    for load_name, load_state in STATE.controllable_loads.items():
        plan_state = PLAN.controllable_loads.get(load_name)
        if not plan_state or not plan_state.is_on:
            continue

        # Calculate the variance between expected and actual consumption
        expected_consumption = plan_state.expected_load_amps
        actual_consumption = load_state.current_load_amps
        variance = expected_consumption - actual_consumption

        # Update variance tracking
        load_state.consumption_variance = variance
        load_state.expected_load_amps = expected_consumption

        # Check if this load has significant unused power
        if (
            variance >= CONFIG.variance_detection_threshold
            and load_state.last_expected_update is not None
            and (now - load_state.last_expected_update).total_seconds()
            >= CONFIG.variance_detection_delay_seconds
        ):
            total_unused_power += variance
            loads_with_unused_power.append(load_name)
            _LOGGER.info(
                "Load %s is using %f A less than expected (%f A), freeing %f A for reallocation",
                load_name,
                actual_consumption,
                expected_consumption,
                variance,
            )

    # If we have significant unused power, trigger reallocation
    if total_unused_power >= CONFIG.variance_detection_threshold:
        _LOGGER.info(
            "Total unused power detected: %f A from loads %s - triggering reallocation",
            total_unused_power,
            loads_with_unused_power,
        )
        # Add the unused power to our available budget and recalculate
        await recalculate_load_control(hass)


@bind_hass
async def calculate_effective_available_power():
    """Calculate available power including power freed by underperforming loads."""
    # Start with the base available power calculation
    safety_margin_amps = CONFIG.hysteresis_amps
    grid_available_amps = CONFIG.max_house_load_amps - STATE.house_consumption_amps

    # Solar power is what is left of solar generation after house consumption
    solar_available_amps = 0.0
    if STATE.solar_generation_kw > 0:
        solar_available_amps = (
            (STATE.solar_generation_kw * 1000) / STATE.mains_voltage
        ) - STATE.house_consumption_amps

        # Safety check to not blow house fuse
        solar_available_amps = min(solar_available_amps, grid_available_amps)

    base_available_amps = 0.0
    if CONFIG.allow_grid_import and STATE.allow_grid_import:
        base_available_amps = grid_available_amps - safety_margin_amps
    elif CONFIG.allow_solar_consumption and solar_available_amps > 0:
        base_available_amps = solar_available_amps - safety_margin_amps

    # Calculate additional power available from loads consuming less than expected
    reactive_available_amps = 0.0
    if CONFIG.enable_reactive_reallocation:
        for load_name, load_state in STATE.controllable_loads.items():
            plan_state = PLAN.controllable_loads.get(load_name)
            if (
                plan_state
                and plan_state.is_on
                and load_state.consumption_variance
                >= CONFIG.variance_detection_threshold
            ):
                reactive_available_amps += load_state.consumption_variance
                _LOGGER.debug(
                    "Adding %f A reactive power from underperforming load %s",
                    load_state.consumption_variance,
                    load_name,
                )

    total_available_amps = base_available_amps + reactive_available_amps
    _LOGGER.debug(
        "Effective available power: base=%f A, reactive=%f A, total=%f A",
        base_available_amps,
        reactive_available_amps,
        total_available_amps,
    )

    return total_available_amps


@bind_hass
@bind_hass
async def recalculate_load_control(hass: HomeAssistant):
    """The core of the load control algorithm."""
    now = datetime.now()
    new_plan = PlanState()

    # Calculate effective available power (including reactive reallocation)
    available_amps = await calculate_effective_available_power()

    new_plan.available_amps = available_amps
    hass.states.async_set("zero_grid.enable_load_control", str(True))
    hass.states.async_set("zero_grid.available_load", str(available_amps))
    _LOGGER.debug("Available amps: %f", available_amps)

    # If the available load we have to play with has not changed meaningfully, do nothing
    # Exception: always recalculate if available power is zero/negative (safety)
    # Also always recalculate if reactive reallocation is enabled (to pick up variance changes)
    available_amps_delta = abs(PLAN.available_amps - available_amps)
    if (
        not CONFIG.enable_reactive_reallocation
        and available_amps_delta < CONFIG.hysteresis_amps
        and available_amps > 0
        and PLAN.available_amps > 0
    ):
        return

    # Build priority list (lower number == more important)
    prioritised_loads = sorted(
        CONFIG.controllable_loads.copy(),
        key=lambda k: CONFIG.controllable_loads[k].priority,
    )
    _LOGGER.debug("Priority: %s", prioritised_loads)

    safety_margin_amps = CONFIG.hysteresis_amps
    overload = (
        STATE.house_consumption_amps > CONFIG.max_house_load_amps - safety_margin_amps
    )

    # Track power freed up by loads that get turned off during this planning cycle
    freed_power_this_cycle = 0.0

    # Loop over controllable loads and determine if they should be on or not
    for load_index, load_name in enumerate(prioritised_loads):
        config = CONFIG.controllable_loads[load_name]
        state = STATE.controllable_loads[load_name]
        previous_plan = PLAN.controllable_loads[load_name]
        plan = new_plan.controllable_loads[load_name] = ControllableLoadPlanState()

        plan.is_on = False
        plan.expected_load_amps = 0

        # Only credit back current load if this load is currently on (will be turned off)
        # Also add any power freed up by higher-priority loads that got turned off
        current_load_credit = state.current_load_amps if state.is_on else 0.0
        _LOGGER.debug(
            "Before credit for %s: available_amps=%f, state.current_load_amps=%f, state.is_on=%s, credit=%f, freed_power=%f",
            load_name,
            available_amps,
            state.current_load_amps,
            state.is_on,
            current_load_credit,
            freed_power_this_cycle,
        )
        available_amps += current_load_credit + freed_power_this_cycle
        freed_power_this_cycle = 0.0  # Reset after adding to available_amps
        _LOGGER.debug(
            "After credit for %s: available_amps=%f", load_name, available_amps
        )

        # Calculate minimum power requirements for all remaining lower-priority loads
        remaining_loads_min_power = 0.0
        for remaining_load_name in prioritised_loads[load_index + 1 :]:
            remaining_config = CONFIG.controllable_loads[remaining_load_name]
            remaining_loads_min_power += remaining_config.min_controllable_load_amps

        # Smart priority allocation: check if we should make room for this load by throttling lower-priority loads
        available_for_this_load = available_amps - remaining_loads_min_power

        # If this load can't fit, check if we can make room by throttling lower-priority throttleable loads
        if (
            available_for_this_load < config.min_controllable_load_amps
            and config.min_controllable_load_amps > 0
        ):
            # Calculate how much power we could free up by throttling lower-priority loads to minimum
            potential_freed_power = 0.0
            for lower_priority_load_name in prioritised_loads[load_index + 1 :]:
                lower_config = CONFIG.controllable_loads[lower_priority_load_name]
                lower_previous_plan = PLAN.controllable_loads[lower_priority_load_name]
                if (
                    lower_config.can_throttle
                    and lower_previous_plan.is_on
                    and lower_previous_plan.throttle_amps
                    > lower_config.min_controllable_load_amps
                ):
                    # Power we could free by throttling this load to minimum
                    freeable_power = (
                        lower_previous_plan.throttle_amps
                        - lower_config.min_controllable_load_amps
                    )
                    potential_freed_power += freeable_power
                    _LOGGER.debug(
                        "Could free %f A from %s (current=%f, min=%f)",
                        freeable_power,
                        lower_priority_load_name,
                        lower_previous_plan.throttle_amps,
                        lower_config.min_controllable_load_amps,
                    )

            # If we can free enough power by throttling, include that in our budget
            if potential_freed_power > 0:
                available_for_this_load += potential_freed_power
                _LOGGER.debug(
                    "Load %s: could free %f A by throttling lower-priority loads, new available=%f",
                    load_name,
                    potential_freed_power,
                    available_for_this_load,
                )

        max_allowable_for_this_load = available_for_this_load

        # Only allocate power if we can meet minimum requirements
        if max_allowable_for_this_load >= config.min_controllable_load_amps:
            will_consume_amps = max(
                config.min_controllable_load_amps,
                min(config.max_controllable_load_amps, max_allowable_for_this_load),
            )
        else:
            # Not enough power available even with throttling
            will_consume_amps = 0.0

        _LOGGER.debug(
            "Load %s planning: available=%f, remaining_min=%f, max_allowable=%f, will_consume=%f",
            load_name,
            available_amps,
            remaining_loads_min_power,
            max_allowable_for_this_load,
            will_consume_amps,
        )

        is_switch_rate_limited = (
            state.last_toggled is not None
            and state.last_toggled
            + timedelta(seconds=config.min_toggle_interval_seconds)
            > now
        )
        is_throttle_rate_limited = (
            state.last_throttled is not None
            and state.last_throttled
            + timedelta(seconds=config.min_throttle_interval_seconds)
            > now
        )

        # Determine if this load should be on
        # If we have no available budget, all loads should be off
        # If will_consume_amps is 0, the load should be off (not enough power for lower-priority loads)
        if new_plan.available_amps <= 0 or will_consume_amps == 0.0:
            should_be_on = False
        else:
            should_be_on = will_consume_amps <= available_amps
        plan.is_on = previous_plan.is_on

        _LOGGER.debug(
            "Load %s planning: should_be_on=%s, will_consume_amps=%f, available_amps=%f, previous_plan.is_on=%s",
            load_name,
            should_be_on,
            will_consume_amps,
            available_amps,
            previous_plan.is_on,
        )

        # Immediately shed load if we are overloading the fuse
        if overload:
            plan.is_on = False
            _LOGGER.debug("Turning load %s off due to overload", load_name)
            # Track power freed up if this load was previously on
            if previous_plan.is_on:
                freed_power_this_cycle += state.current_load_amps
                _LOGGER.debug(
                    "Load %s turning off frees up %f A for lower-priority loads",
                    load_name,
                    state.current_load_amps,
                )
        elif should_be_on != plan.is_on:
            if not is_switch_rate_limited:
                plan.is_on = should_be_on
                if plan.is_on:
                    _LOGGER.debug("Planning to turn load %s on", load_name)
                else:
                    _LOGGER.debug("Planning to turn load %s off", load_name)
                    # Track power freed up if this load was previously on and is being turned off
                    if previous_plan.is_on and not plan.is_on:
                        freed_power_this_cycle += state.current_load_amps
                        _LOGGER.debug(
                            "Load %s turning off frees up %f A for lower-priority loads",
                            load_name,
                            state.current_load_amps,
                        )
            else:
                _LOGGER.debug("Unable to change load %s due to rate limit", load_name)
        else:
            _LOGGER.debug("Load %s plan unchanged: is_on=%s", load_name, plan.is_on)

        # Account for expected load in budget
        if plan.is_on:
            plan.expected_load_amps = will_consume_amps
            new_plan.used_amps += will_consume_amps
            _LOGGER.debug(
                "Before subtraction for %s: available_amps=%f, will_consume_amps=%f",
                load_name,
                available_amps,
                will_consume_amps,
            )
            available_amps -= will_consume_amps
            _LOGGER.debug(
                "After subtraction for %s: available_amps=%f", load_name, available_amps
            )

            # Set throttle value for throttleable loads
            if config.can_throttle:
                plan.throttle_amps = will_consume_amps
                _LOGGER.debug(
                    "Setting throttle for %s: will_consume_amps=%f -> plan.throttle_amps=%f",
                    load_name,
                    will_consume_amps,
                    plan.throttle_amps,
                )
            else:
                plan.throttle_amps = 0.0
        else:
            plan.throttle_amps = 0.0

        if config.can_throttle and is_throttle_rate_limited:
            # We won't change the expected load due to throttling
            will_consume_amps = previous_plan.expected_load_amps
            _LOGGER.debug("Unable to throttle load %s due to rate limit", load_name)

    hass.states.async_set("zero_grid.controlled_load", str(new_plan.used_amps))

    # Post-planning adjustment: throttle down lower-priority loads to make room for higher-priority loads
    for load_index, load_name in enumerate(prioritised_loads):
        config = CONFIG.controllable_loads[load_name]
        previous_plan = PLAN.controllable_loads[load_name]
        new_plan_load = new_plan.controllable_loads[load_name]

        # If this load is turning on and needs power, check if we need to throttle lower-priority loads
        if (
            new_plan_load.is_on
            and not previous_plan.is_on
            and new_plan_load.throttle_amps > 0
        ):
            power_needed = new_plan_load.throttle_amps
            power_available = (
                new_plan.available_amps - new_plan.used_amps
            )  # Remaining unused power

            if power_available < power_needed:
                power_to_free = power_needed - power_available
                _LOGGER.debug(
                    "Load %s turning on needs %f A, only %f A available, need to free %f A",
                    load_name,
                    power_needed,
                    power_available,
                    power_to_free,
                )

                # Throttle down lower-priority loads to free up power
                power_freed = 0.0
                for lower_priority_load_name in prioritised_loads[load_index + 1 :]:
                    if power_freed >= power_to_free:
                        break

                    lower_config = CONFIG.controllable_loads[lower_priority_load_name]
                    lower_new_plan = new_plan.controllable_loads[
                        lower_priority_load_name
                    ]

                    if (
                        lower_config.can_throttle
                        and lower_new_plan.is_on
                        and lower_new_plan.throttle_amps
                        > lower_config.min_controllable_load_amps
                    ):
                        # Calculate how much we can throttle this load down
                        current_throttle = lower_new_plan.throttle_amps
                        min_throttle = lower_config.min_controllable_load_amps
                        max_reduction = current_throttle - min_throttle

                        # Throttle down by the minimum needed or maximum possible
                        reduction_needed = min(
                            max_reduction, power_to_free - power_freed
                        )
                        new_throttle = current_throttle - reduction_needed

                        _LOGGER.debug(
                            "Throttling %s from %f A to %f A (reduction=%f A) to make room for %s",
                            lower_priority_load_name,
                            current_throttle,
                            new_throttle,
                            reduction_needed,
                            load_name,
                        )

                        lower_new_plan.throttle_amps = new_throttle
                        lower_new_plan.expected_load_amps = new_throttle
                        new_plan.used_amps -= reduction_needed
                        power_freed += reduction_needed

    # Validate that we haven't planned more consumption than we have available from solar
    if new_plan.used_amps > new_plan.available_amps:
        over_allocation = new_plan.used_amps - new_plan.available_amps
        _LOGGER.error(
            "CRITICAL: Power over-allocation detected! Planned %f A but only %f A available (over by %f A)",
            new_plan.used_amps,
            new_plan.available_amps,
            over_allocation,
        )

        # Emergency reduction: turn off lowest priority loads until we're within budget
        for load_name in reversed(prioritised_loads):
            if new_plan.used_amps <= new_plan.available_amps:
                break

            plan_load = new_plan.controllable_loads[load_name]
            if plan_load.is_on:
                _LOGGER.warning(
                    "Emergency turn-off of %s to prevent over-allocation (was using %f A)",
                    load_name,
                    plan_load.expected_load_amps,
                )
                new_plan.used_amps -= plan_load.expected_load_amps
                plan_load.is_on = False
                plan_load.expected_load_amps = 0
                plan_load.throttle_amps = 0

    _LOGGER.debug(
        "Planning complete: initial_available=%f, planned_used=%f",
        new_plan.available_amps,
        new_plan.used_amps,
    )

    await execute_plan(hass, new_plan)


@bind_hass
async def execute_plan(hass: HomeAssistant, plan: PlanState):
    """Changes entity states to acheive laod control plan."""
    now = datetime.now()

    for load_name in plan.controllable_loads:  # pylint: disable=consider-using-dict-items
        config = CONFIG.controllable_loads[load_name]
        state = STATE.controllable_loads[load_name]
        previous_plan = PLAN.controllable_loads[load_name]
        new_plan = plan.controllable_loads[load_name]

        _LOGGER.debug(
            "Executing plan for load %s: new_plan.is_on=%s, previous_plan.is_on=%s, state.is_on=%s",
            load_name,
            new_plan.is_on,
            previous_plan.is_on,
            state.is_on,
        )

        # Turn on or off load only when we need to
        switch_domain = parse_entity_domain(config.switch_entity)

        # Check if entity exists before attempting service calls
        if hass.states.get(config.switch_entity) is None:
            _LOGGER.error(
                "Switch entity %s does not exist, skipping control",
                config.switch_entity,
            )
            continue  # Skip this load and continue with the next one

        if new_plan.is_on and not state.is_on:
            _LOGGER.info("Turning on %s due to available load", config.switch_entity)
            _LOGGER.debug(
                "Turn-on condition: new_plan.is_on=%s, state.is_on=%s",
                new_plan.is_on,
                state.is_on,
            )
            _LOGGER.debug(
                "Service call: %s.turn_on with entity_id=%s",
                switch_domain,
                config.switch_entity,
            )
            try:
                # Use domain-specific service calls for better compatibility
                service_name = "turn_on"
                await hass.services.async_call(
                    switch_domain,
                    service_name,
                    {"entity_id": config.switch_entity},
                    blocking=True,  # Wait for completion to ensure success
                )
                state.last_toggled = now
                state.is_on_load_control = True
                _LOGGER.debug("Successfully turned on %s", config.switch_entity)
            except (ValueError, KeyError, RuntimeError) as err:
                _LOGGER.error("Failed to turn on %s: %s", config.switch_entity, err)
        elif not new_plan.is_on and state.is_on:
            _LOGGER.info("Turning off %s due to available load", config.switch_entity)
            _LOGGER.debug(
                "Turn-off condition: new_plan.is_on=%s, state.is_on=%s",
                new_plan.is_on,
                state.is_on,
            )
            _LOGGER.debug(
                "Service call: %s.turn_off with entity_id=%s",
                switch_domain,
                config.switch_entity,
            )
            try:
                # Use domain-specific service calls for better compatibility
                service_name = "turn_off"
                await hass.services.async_call(
                    switch_domain,
                    service_name,
                    {"entity_id": config.switch_entity},
                    blocking=True,  # Wait for completion to ensure success
                )
                state.last_toggled = now
                state.is_on_load_control = False
                _LOGGER.debug("Successfully turned off %s", config.switch_entity)
            except (ValueError, KeyError, RuntimeError) as err:
                _LOGGER.error("Failed to turn off %s: %s", config.switch_entity, err)
        else:
            _LOGGER.debug(
                "No action needed for load %s: new_plan.is_on=%s, state.is_on=%s",
                load_name,
                new_plan.is_on,
                state.is_on,
            )

        # Adjust load throttling
        if config.can_throttle:
            _LOGGER.debug(
                "Throttle check for %s: can_throttle=%s, state.is_on_load_control=%s, new_plan.is_on=%s",
                load_name,
                config.can_throttle,
                state.is_on_load_control,
                new_plan.is_on,
            )

        if (
            config.can_throttle and new_plan.is_on
        ):  # Removed is_on_load_control requirement
            # Check if throttle entity exists
            if hass.states.get(config.throttle_amps_entity) is None:
                _LOGGER.error(
                    "Throttle entity %s does not exist, skipping throttling",
                    config.throttle_amps_entity,
                )
            else:
                # Make sure the delta is significant enough before issuing command
                throttle_delta = previous_plan.throttle_amps - new_plan.throttle_amps
                _LOGGER.debug(
                    "Throttle delta for %s: previous=%f, new=%f, delta=%f, hysteresis=%f",
                    load_name,
                    previous_plan.throttle_amps,
                    new_plan.throttle_amps,
                    abs(throttle_delta),
                    CONFIG.hysteresis_amps,
                )
                if abs(throttle_delta) > CONFIG.hysteresis_amps:
                    _LOGGER.info(
                        "Throttling %s to %f due to available load",
                        config.throttle_amps_entity,
                        new_plan.throttle_amps,
                    )
                    number_domain = parse_entity_domain(config.throttle_amps_entity)
                    _LOGGER.debug(
                        "Service call: %s.set_value with entity_id=%s, value=%f",
                        number_domain,
                        config.throttle_amps_entity,
                        new_plan.throttle_amps,
                    )
                    try:
                        # Use domain-specific service for number entities
                        service_name = "set_value"
                        service_data = {
                            "entity_id": config.throttle_amps_entity,
                            "value": new_plan.throttle_amps,  # Don't convert to string
                        }
                        await hass.services.async_call(
                            number_domain,
                            service_name,
                            service_data,
                            blocking=True,  # Wait for completion to ensure success
                        )
                        state.last_throttled = now
                        _LOGGER.debug(
                            "Successfully throttled %s to %f",
                            config.throttle_amps_entity,
                            new_plan.throttle_amps,
                        )
                    except (ValueError, KeyError, RuntimeError) as err:
                        _LOGGER.error(
                            "Failed to throttle %s: %s",
                            config.throttle_amps_entity,
                            err,
                        )
                else:
                    # Don't update the throttle due to hysteresis, but keep the new plan value
                    _LOGGER.debug(
                        "Throttle unchanged for %s: delta %f <= hysteresis %f (keeping new plan value %f)",
                        load_name,
                        abs(throttle_delta),
                        CONFIG.hysteresis_amps,
                        new_plan.throttle_amps,
                    )
        elif config.can_throttle:
            _LOGGER.debug(
                "Skipping throttle for %s: new_plan.is_on=%s", load_name, new_plan.is_on
            )

        # Update expected consumption tracking for reactive reallocation
        if CONFIG.enable_reactive_reallocation:
            # Update expected consumption in state for variance tracking
            state.expected_load_amps = new_plan.expected_load_amps
            state.last_expected_update = now
        PLAN.available_amps = plan.available_amps
        PLAN.used_amps = plan.used_amps
        # Deep copy the controllable loads to avoid reference sharing between PLAN and new_plan
        PLAN.controllable_loads = {}
        for load_name, load_plan in plan.controllable_loads.items():
            PLAN.controllable_loads[load_name] = ControllableLoadPlanState()
            PLAN.controllable_loads[load_name].is_on = load_plan.is_on
            PLAN.controllable_loads[
                load_name
            ].expected_load_amps = load_plan.expected_load_amps
            PLAN.controllable_loads[load_name].throttle_amps = load_plan.throttle_amps

    _LOGGER.debug("Plan execution completed for %d loads", len(plan.controllable_loads))


@bind_hass
async def safety_abort(hass: HomeAssistant):
    """Cuts all load controlled by the integration in a safety situation."""
    _LOGGER.error("Aborting load control, cutting all loads")

    plan = PlanState()
    plan.available_amps = 0
    plan.controllable_loads = 0
    plan.used_amps = 0
    for control in CONFIG.controllable_loads.values():
        load_plan = ControllableLoadPlanState()
        load_plan.is_on = False
        load_plan.expected_load_amps = 0
        plan.controllable_loads[control.name] = load_plan

    await execute_plan(hass, plan)
