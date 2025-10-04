"""The ZeroGrid integration."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta
import logging

from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .config import Config, ControllableLoadConfig
from .const import DOMAIN
from .helpers import parse_entity_domain
from .state import ControllableLoadState, State, PlanState, ControllableLoadPlanState

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = []

CONFIG = Config()
STATE = State()
PLAN = PlanState()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Main entry point on startup."""

    domain_config = config[DOMAIN]
    parse_config(domain_config)
    initialise_state(hass)
    subscribe_to_entity_changes(hass)

    return True


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
    for control in CONFIG.controllable_loads.values():
        STATE.controllable_loads[control.name] = ControllableLoadState()
        PLAN.controllable_loads[control.name] = ControllableLoadPlanState()

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
        # if control.throttle_amps_entity is not None:
        #     entity_ids.append(control.throttle_amps_entity)

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
                _LOGGER.warning(
                    "House consumption entity is unavailable, cutting all load for safety"
                )
                abort_load_control()
                return

        elif entity_id == CONFIG.mains_voltage_entity:
            if new_state is not None:
                STATE.mains_voltage = float(new_state.state)
            else:
                _LOGGER.warning(
                    "Mains voltage entity is unavailable, cutting all load for safety"
                )
                abort_load_control()
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
            # match to controllable loads
            for control in CONFIG.controllable_loads.values():
                if entity_id == control.load_amps_entity:
                    if new_state is not None:
                        STATE.controllable_loads[
                            control.name
                        ].current_load_amps = float(new_state.state)
                    else:
                        STATE.controllable_loads[control.name].current_load_amps = 0.0

                if entity_id == control.switch_entity:
                    if new_state is not None:
                        STATE.controllable_loads[control.name].is_on = (
                            new_state.state.lower() == "on"
                        )
                    else:
                        STATE.controllable_loads[
                            control.name
                        ].is_on = True  # Assume on if unavailable

        await recalculate_load_control(hass)

    async def state_time_listener(now: datetime) -> None:
        _LOGGER.debug("Time listener fired")
        await recalculate_load_control(hass)

    _LOGGER.debug("Subscribing... %s", entity_ids)
    async_track_state_change_event(hass, entity_ids, state_automation_listener)

    interval = timedelta(seconds=CONFIG.recalculate_interval_seconds)
    async_track_time_interval(hass, state_time_listener, interval)


@bind_hass
async def recalculate_load_control(hass: HomeAssistant):
    """The core of the loac control algorithm."""
    now = datetime.now()
    new_plan = PlanState()

    # Determine how much power we have to work with
    # Grid power is what is left of the house fuse after house consumption
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

    available_amps = 0.0
    if CONFIG.allow_grid_import and STATE.allow_grid_import:
        available_amps = grid_available_amps - safety_margin_amps  # Can use grid power
    elif CONFIG.allow_solar_consumption and solar_available_amps > 0:
        available_amps = (
            solar_available_amps - safety_margin_amps
        )  # Can only use solar power

    # If the available load we have to play with has not changed meaningfully, do nothing
    available_amps_delta = abs(PLAN.available_amps - available_amps)
    if available_amps_delta < CONFIG.hysteresis_amps:
        return

    new_plan.available_amps = available_amps
    hass.states.async_set("zero_grid.available_amps", str(available_amps))
    _LOGGER.debug("Available amps: %f", available_amps)

    # Build priority list (lower number == more important)
    prioritised_loads = sorted(
        CONFIG.controllable_loads.copy(),
        key=lambda k: CONFIG.controllable_loads[k].priority,
        reverse=True,
    )
    _LOGGER.debug("Priority: %s", prioritised_loads)

    if available_amps > CONFIG.hysteresis_amps:
        load_increase_budget = available_amps
        _LOGGER.debug("Load increase budget: %s", load_increase_budget)

        # Figure out what the
        for load_name in CONFIG.controllable_loads:  # pylint: disable=consider-using-dict-items
            config = CONFIG.controllable_loads[load_name]
            state = STATE.controllable_loads[load_name]
            plan = new_plan.controllable_loads[load_name] = ControllableLoadPlanState()

            if state.is_on and not config.can_throttle:
                _LOGGER.debug("Load %s already on and cannot throttle", load_name)
                continue

            # Account for any current load in the budget
            if state.is_on:
                load_increase_budget += state.current_load_amps

            # Determine how much load we would consume if we turned this on
            will_consume_amps = max(
                config.min_controllable_load_amps,
                min(config.max_controllable_load_amps, load_increase_budget),
            )
            if will_consume_amps > load_increase_budget:
                _LOGGER.debug("Load %s is too large to turn on", load_name)
                continue

            if not state.is_on:
                # We are currently off, so we can only turn on if we meet min toggle interval
                if (
                    state.last_toggled is None
                    or state.last_toggled
                    + timedelta(seconds=config.min_toggle_interval_seconds)
                    <= now
                ):
                    plan.is_on = True
                    expected_amps =

                    plan.expected_load_amps = max(config.min_controllable_load_amps, config.max_controllable_load_amps)

                else:
                    _LOGGER.debug(
                        "Unable to turn on load %s due to rate limit", load_name
                    )

            if config.can_throttle:
                if (
                    state.last_throttled is None
                    or state.last_throttled
                    + timedelta(seconds=config.min_throttle_interval_seconds)
                    <= now
                ):
                    # Set the throttling current
                    state.last_throttled = now

                    number_domain = parse_entity_domain(config.throttle_amps_entity)
                    hass.services.call(
                        number_domain,
                        "set_value",
                        {
                            "entity_id": config.throttle_amps_entity,
                            "value": will_consume_amps,
                        },
                    )
                    state.last_throttled = now
                    state.is_on_load_control = True
                else:
                    _LOGGER.debug(
                        "Unable to throttle load %s due to rate limit", load_name
                    )

    elif available_amps < CONFIG.hysteresis_amps:
        # Turn off loads in reverse priority order until we are within available amps
        load_decrease_budget = available_amps - CONFIG.hysteresis_amps
        _LOGGER.debug("Load increase budget: %s", load_decrease_budget)

    else:
        _LOGGER.debug("No load available, within safety margin:")

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

        # Turn on or off load only when we need to
        switch_domain = parse_entity_domain(config.switch_entity)
        if new_plan.is_on and not previous_plan.is_on and not state.is_on:
            _LOGGER.info("Turning on %s due to available load", config.switch_entity)
            state.last_toggled = now
            state.is_on_load_control = True

            await hass.services.async_call(
                switch_domain,
                "turn_on",
                {"entity_id": config.switch_entity},
                blocking=False,
            )
        elif not new_plan.is_on and not previous_plan.is_on and state.is_on:
            _LOGGER.info("Turning off %s due to available load", config.switch_entity)
            state.last_toggled = now
            state.is_on_load_control = False

            await hass.services.async_call(
                switch_domain,
                "turn_off",
                {"entity_id": config.switch_entity},
                blocking=False,
            )

        # Adjust load throttling
        if config.can_throttle:
            # Make sure the delta is significant enough before issuing command
            throttle_delta = previous_plan.throttle_amps - new_plan.throttle_amps
            if abs(throttle_delta) > CONFIG.hysteresis_amps:
                if state.is_on_load_control:
                    _LOGGER.info(
                        "Throttling %s to %d due to available load",
                        config.throttle_amps_entity,
                        new_plan.throttle_amps,
                    )
                    number_domain = parse_entity_domain(config.throttle_amps_entity)
                    state.last_throttled = now

                    hass.services.call(
                        number_domain,
                        "set_value",
                        {
                            "entity_id": config.throttle_amps_entity,
                            "value": str(new_plan.throttle_amps),
                        },
                        blocking=False,
                    )
            else:
                # Since we never changed the throttle, update the plan
                new_plan.throttle_amps = previous_plan.throttle_amps

        # Update current plan with new plan
        PLAN.available_amps = plan.available_amps
        PLAN.controllable_loads = plan.controllable_loads


def abort_load_control():
    """Cuts all load controlled by the integtration in a safety situation."""
    _LOGGER.error("Aborting load control, cutting all loads")
