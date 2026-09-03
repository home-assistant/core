"""Shared state for Prism solar battery balancing."""

from dataclasses import dataclass

from .const import DOMAIN

SOLAR_BALANCE_DISABLED = "disabled"
SOLAR_BALANCE_WAITING_DATA = "waiting_data"
SOLAR_BALANCE_WAITING_BATTERY_DATA = "waiting_battery_data"
SOLAR_BALANCE_WAITING_SOLAR_MODE = "waiting_solar_mode"
SOLAR_BALANCE_WAITING_STABLE_SURPLUS = "waiting_stable_surplus"
SOLAR_BALANCE_PAUSED_LOW_SURPLUS = "paused_low_surplus"
SOLAR_BALANCE_EXTERNAL_PAUSED = "external_paused"
SOLAR_BALANCE_CHARGING_SURPLUS = "charging_surplus"
SOLAR_BALANCE_LOW_SURPLUS_KEEP_CHARGING = "low_surplus_keep_charging"

SURPLUS_SOURCE_SOLAR_HOME_LOAD = "solar_home_load"
SURPLUS_SOURCE_PRISM_GRID_BATTERY = "prism_grid_battery"


@dataclass(slots=True)
class SolarBalanceState:
    """Store one complete balancing decision for diagnostics.

    The switch entity owns the control loop; sensor entities only render this
    snapshot so users can see why the controller changed, held or skipped
    current.
    """

    status: str = SOLAR_BALANCE_WAITING_DATA
    surplus_current: float | None = None
    available_power: float | None = None
    target_power: float | None = None
    start_delay_remaining: int | None = None
    grid_power: float | None = None
    ev_power: float | None = None
    solar_power: float | None = None
    home_load_power: float | None = None
    battery_power: float | None = None
    battery_charge_power: float | None = None
    battery_discharge_power: float | None = None
    battery_power_used: float | None = None
    battery_max_charge_power: float | None = None
    battery_soc: float | None = None
    battery_reserve_power: float | None = None
    battery_reserve_shortfall_power: float | None = None
    surplus_source: str | None = None
    target_export_power: float | None = None
    deadband_power: float | None = None
    raw_target_current: float | None = None
    target_current: float | None = None
    theoretical_target_current: float | None = None
    reported_current_limit: float | None = None
    unused_export_power: float | None = None
    excess_import_power: float | None = None
    residual_export_remaining: int | None = None
    deadband_active: bool | None = None
    ramp_limited: bool | None = None
    ramp_direction: str | None = None
    current_limit_reason: str | None = None
    decision_reason: str | None = None
    decision_summary: str | None = None
    missing_data_reason: str | None = None
    dry_run: bool = False


@dataclass(slots=True, frozen=True)
class BatteryPowerBreakdown:
    """Normalized battery power values used by the balancer.

    Positive normalized power means discharge, negative means charge.
    """

    normalized_power: float
    charge_power: float
    discharge_power: float
    charge_available_above_reserve: float
    power_to_exclude: float


@dataclass(slots=True, frozen=True)
class AvailablePowerResult:
    """Calculated EV surplus and the source used for the calculation."""

    available_power: float
    source: str
    effective_home_load_power: float | None


def normalize_battery_power(
    battery_power: float,
    battery_discharge_positive: bool,
    battery_reserve_power: float,
    use_battery_charge: bool,
) -> BatteryPowerBreakdown:
    """Normalize battery power and return the pieces used by the algorithm."""
    normalized_power = battery_power if battery_discharge_positive else -battery_power
    charge_power = max(-normalized_power, 0)
    discharge_power = max(normalized_power, 0)
    charge_available = max(charge_power - battery_reserve_power, 0)
    power_to_exclude = discharge_power - (charge_available if use_battery_charge else 0)
    return BatteryPowerBreakdown(
        normalized_power=normalized_power,
        charge_power=charge_power,
        discharge_power=discharge_power,
        charge_available_above_reserve=charge_available,
        power_to_exclude=power_to_exclude,
    )


def get_battery_reserve_power(
    battery_soc: float | None,
    battery_max_charge_power: float,
    soc_mid: float,
    soc_high: float,
    mid_reserve_power: float,
    high_reserve_power: float,
) -> float:
    """Return how much battery charge power should be reserved."""
    if battery_soc is None:
        return battery_max_charge_power
    if battery_soc >= 95:
        return 0
    if battery_soc >= soc_high:
        return high_reserve_power
    if battery_soc >= soc_mid:
        return mid_reserve_power
    return battery_max_charge_power


def calculate_available_power(
    *,
    ev_power: float,
    grid_power: float,
    battery_charge_available: float,
    battery_reserve_shortfall: float,
    battery_power_to_exclude: float,
    use_battery_charge: bool,
    solar_power: float | None = None,
    home_load_power: float | None = None,
    home_load_includes_ev: bool = False,
) -> AvailablePowerResult:
    """Return EV surplus power from direct sensors or Prism fallback data."""
    if solar_power is not None and home_load_power is not None:
        solar_production = max(solar_power, 0)
        effective_home_load = max(home_load_power, 0)
        if home_load_includes_ev:
            effective_home_load = max(effective_home_load - ev_power, 0)
        available_power = (
            solar_production - effective_home_load - max(battery_reserve_shortfall, 0)
        )
        if use_battery_charge and available_power > 0:
            available_power += battery_charge_available
        return AvailablePowerResult(
            available_power=available_power,
            source=SURPLUS_SOURCE_SOLAR_HOME_LOAD,
            effective_home_load_power=effective_home_load,
        )

    return AvailablePowerResult(
        available_power=(
            ev_power
            - grid_power
            - battery_power_to_exclude
            - max(battery_reserve_shortfall, 0)
        ),
        source=SURPLUS_SOURCE_PRISM_GRID_BATTERY,
        effective_home_load_power=None,
    )


def describe_solar_balance_state(  # noqa: C901
    state: SolarBalanceState, language: str | None = None
) -> str:
    """Return a concise human-readable explanation for the latest decision."""
    reason = state.current_limit_reason or state.decision_reason or state.status
    is_italian = (language or "").lower().startswith("it")
    target = (
        f"{state.target_current:g}A"
        if isinstance(state.target_current, (int, float))
        else ("nessuna corrente" if is_italian else "no current")
    )
    available = (
        f"{state.available_power:.0f}W"
        if isinstance(state.available_power, (int, float))
        else ("surplus sconosciuto" if is_italian else "unknown surplus")
    )
    context = _describe_decision_context(state, is_italian)

    if is_italian:
        if state.dry_run and isinstance(state.target_current, (int, float)):
            return (
                f"Simulazione: comanderei {target} in modalita solare, "
                f"ma non invio MQTT. {context}"
            ).strip()
        if (
            reason in ("low_surplus_hold_6a", "target_current")
            and isinstance(state.target_current, (int, float))
            and isinstance(state.reported_current_limit, (int, float))
            and round(state.reported_current_limit) != round(state.target_current)
        ):
            return (
                f"Richiedo {target}: Prism riporta ancora pilot "
                f"{state.reported_current_limit:g}A."
            )
        if reason == "low_surplus_hold_6a":
            return _with_context(
                f"Mantengo 6A: il surplus calcolato e basso ({available}).",
                context,
            )
        if reason == "residual_export_recovery":
            return _with_context(
                f"Salgo a {target}: l'esportazione residua e rimasta disponibile "
                "abbastanza a lungo.",
                context,
            )
        if reason == "battery_charge_target":
            return _with_context(
                f"Salgo a {target}: la batteria sta caricando oltre la riserva "
                "configurata.",
                context,
            )
        if reason == "deadband_hold":
            return _with_context(
                f"Mantengo {target}: import/export dalla rete e dentro la banda morta.",
                context,
            )
        if reason == "waiting_stable_surplus":
            remaining = state.start_delay_remaining or 0
            return _with_context(
                f"Attendo {remaining}s: il surplus deve restare stabile prima "
                "di aumentare.",
                context,
            )
        if reason == "restart_min_current":
            return _with_context(
                "Riparto da 6A: dopo un blocco per surplus basso non uso il "
                "vecchia soglia corrente come base.",
                context,
            )
        if reason == "waiting_solar_mode":
            return _with_context(
                "Attendo: Prism non e in modalita solare, quindi non invio "
                "corrente o modalita.",
                context,
            )
        if reason == "autolimit_low_surplus":
            return (
                "Attendo: l'autolimit Prism e attivo e l'import dalla rete e "
                "ancora troppo alto."
            )
        if reason == "autolimit_wait_stable_surplus":
            remaining = state.residual_export_remaining or 0
            return (
                f"Attendo {remaining}s: l'autolimit Prism e attivo e serve "
                "export stabile prima del recupero."
            )
        if reason == "autolimit_recovery_6a":
            return (
                "Provo il recupero a 6A: l'autolimit Prism e rientrato nella "
                "banda morta."
            )
        if reason == "external_pause":
            if isinstance(state.theoretical_target_current, (int, float)):
                return (
                    "Pausa da Prism o app: non invio setpoint alla wallbox. "
                    f"Target teorico {state.theoretical_target_current:g}A."
                )
            return (
                "Pausa da Prism o app: l'integrazione non riavvia la carica "
                "automaticamente."
            )
        if reason == "ramp_up_wait":
            return _with_context(
                f"Mantengo {target}: attendo il prossimo intervallo consentito "
                "per aumentare.",
                context,
            )
        if reason in ("ramp_up_limited", "ramp_down_limited"):
            return _with_context(
                f"Mi sposto a {target}: la rampa sta rendendo graduale la variazione.",
                context,
            )
        if state.status == SOLAR_BALANCE_CHARGING_SURPLUS:
            return _with_context(
                f"Carico a {target}: surplus disponibile ({available}).",
                context,
            )
        if state.status == SOLAR_BALANCE_DISABLED:
            return "Bilanciamento solare disattivato."
        if state.status == SOLAR_BALANCE_WAITING_DATA:
            if state.missing_data_reason:
                return f"In attesa dei dati necessari: {state.missing_data_reason}."
            return "In attesa dei dati necessari dai sensori."
        if state.status == SOLAR_BALANCE_WAITING_BATTERY_DATA:
            return "In attesa del dato potenza batteria."
        if state.status == SOLAR_BALANCE_WAITING_SOLAR_MODE:
            return "In attesa della modalita solare Prism."
        return f"Decisione: {reason or state.status}."

    if state.dry_run and isinstance(state.target_current, (int, float)):
        return (
            f"Dry run: would request {target} and solar mode, but no MQTT "
            f"command is sent. {context}"
        ).strip()
    if (
        reason in ("low_surplus_hold_6a", "target_current")
        and isinstance(state.target_current, (int, float))
        and isinstance(state.reported_current_limit, (int, float))
        and round(state.reported_current_limit) != round(state.target_current)
    ):
        return (
            f"Requesting {target}: Prism is still reporting pilot "
            f"{state.reported_current_limit:g}A."
        )
    if reason == "low_surplus_hold_6a":
        return _with_context(
            f"Holding 6A: calculated surplus is low ({available}).",
            context,
        )
    if reason == "residual_export_recovery":
        return _with_context(
            f"Raising to {target}: residual export stayed available long enough.",
            context,
        )
    if reason == "battery_charge_target":
        return _with_context(
            f"Raising to {target}: battery is charging above the configured reserve.",
            context,
        )
    if reason == "deadband_hold":
        return _with_context(
            f"Holding {target}: grid import/export is inside the deadband.",
            context,
        )
    if reason == "waiting_stable_surplus":
        remaining = state.start_delay_remaining or 0
        return _with_context(
            f"Waiting {remaining}s: surplus must stay stable before increasing.",
            context,
        )
    if reason == "restart_min_current":
        return _with_context(
            "Restarting from 6A: after a low-surplus block, the old current "
            "limit is not used as the ramp base.",
            context,
        )
    if reason == "waiting_solar_mode":
        return _with_context(
            "Waiting: Prism is not in solar mode, so the integration will not "
            "command current or mode.",
            context,
        )
    if reason == "autolimit_low_surplus":
        return "Waiting: Prism autolimit is active and grid import is still too high."
    if reason == "autolimit_wait_stable_surplus":
        remaining = state.residual_export_remaining or 0
        return (
            f"Waiting {remaining}s: Prism autolimit is active and stable export "
            "is required before recovery."
        )
    if reason == "autolimit_recovery_6a":
        return "Trying 6A recovery: Prism autolimit cleared inside the deadband."
    if reason == "external_pause":
        if isinstance(state.theoretical_target_current, (int, float)):
            return (
                "Paused by Prism or app: the integration will not command the "
                f"wallbox. Theoretical target {state.theoretical_target_current:g}A."
            )
        return "Paused by Prism or app: the integration will not resume automatically."
    if reason == "ramp_up_wait":
        return _with_context(
            f"Holding {target}: waiting for the next allowed ramp-up interval.",
            context,
        )
    if reason in ("ramp_up_limited", "ramp_down_limited"):
        return _with_context(
            f"Moving to {target}: ramp limit is smoothing the current change.",
            context,
        )
    if state.status == SOLAR_BALANCE_CHARGING_SURPLUS:
        return _with_context(
            f"Charging at {target}: surplus is available ({available}).",
            context,
        )
    if state.status == SOLAR_BALANCE_DISABLED:
        return "Solar balancing is disabled."
    if state.status == SOLAR_BALANCE_WAITING_DATA:
        if state.missing_data_reason:
            return f"Waiting for required sensor data: {state.missing_data_reason}."
        return "Waiting for required sensor data."
    if state.status == SOLAR_BALANCE_WAITING_BATTERY_DATA:
        return "Waiting for battery power data."
    if state.status == SOLAR_BALANCE_WAITING_SOLAR_MODE:
        return "Waiting for Prism solar mode."
    return f"Decision: {reason or state.status}."


def _describe_decision_context(state: SolarBalanceState, is_italian: bool) -> str:
    """Return the dominant constraint and next release condition."""
    if state.missing_data_reason:
        if is_italian:
            return f"Vincolo: manca {state.missing_data_reason}."
        return f"Constraint: missing {state.missing_data_reason}."

    if state.current_limit_reason == "waiting_stable_surplus":
        remaining = state.start_delay_remaining or 0
        if is_italian:
            return f"Vincolo: surplus non ancora stabile. Prossimo sblocco tra {remaining}s."
        return f"Constraint: surplus is not stable yet. Next release in {remaining}s."

    if state.current_limit_reason == "ramp_up_wait":
        if is_italian:
            return "Vincolo: intervallo minimo tra aumenti corrente."
        return "Constraint: minimum current increase interval."

    if state.current_limit_reason == "restart_min_current":
        if is_italian:
            return "Vincolo: ripartenza prudente dal minimo Type 2."
        return "Constraint: conservative restart from the Type 2 minimum."

    if state.current_limit_reason in ("ramp_up_limited", "ramp_down_limited"):
        if is_italian:
            return "Vincolo: rampa graduale per evitare oscillazioni."
        return "Constraint: ramp limit is smoothing the current change."

    if state.current_limit_reason == "deadband_hold":
        if is_italian:
            return "Vincolo: rete dentro la banda morta."
        return "Constraint: grid import/export is inside the deadband."

    if state.current_limit_reason == "battery_charge_target":
        reserve = _format_watts(state.battery_reserve_power, is_italian)
        charge = _format_watts(state.battery_charge_power, is_italian)
        if is_italian:
            return f"Vincolo: batteria sopra la riserva ({charge} > {reserve})."
        return f"Constraint: battery charge is above reserve ({charge} > {reserve})."

    if state.current_limit_reason == "residual_export_recovery":
        export = _format_watts(state.unused_export_power, is_italian)
        if is_italian:
            return f"Vincolo: export residuo disponibile ({export})."
        return f"Constraint: residual export is available ({export})."

    if state.decision_reason == SOLAR_BALANCE_EXTERNAL_PAUSED:
        if is_italian:
            return "Vincolo: pausa comandata da Prism o app."
        return "Constraint: Prism or app pause."

    if state.current_limit_reason == "low_surplus_hold_6a":
        available = _format_watts(state.available_power, is_italian)
        if is_italian:
            return f"Vincolo: surplus sotto il minimo Type 2 ({available})."
        return f"Constraint: surplus is below the Type 2 minimum ({available})."

    if (
        state.battery_reserve_shortfall_power
        and state.battery_reserve_shortfall_power > 0
    ):
        shortfall = _format_watts(state.battery_reserve_shortfall_power, is_italian)
        if is_italian:
            return f"Vincolo: mancano {shortfall} alla riserva batteria."
        return f"Constraint: battery reserve is short by {shortfall}."

    if isinstance(state.available_power, (int, float)):
        available = _format_watts(state.available_power, is_italian)
        if is_italian:
            return f"Surplus calcolato: {available}."
        return f"Calculated surplus: {available}."

    return ""


def _with_context(message: str, context: str) -> str:
    """Append diagnostic context when available."""
    if not context:
        return message
    return f"{message} {context}"


def _format_watts(value: float | None, is_italian: bool) -> str:
    """Format power for diagnostic summaries."""
    if not isinstance(value, (int, float)):
        return "sconosciuto" if is_italian else "unknown"
    return f"{value:.0f}W"


def get_solar_balance_signal(serial: str, port: int) -> str:
    """Return the dispatcher signal for one Prism solar balance port."""
    return f"{DOMAIN}_solar_balance_{serial}_{port}"
