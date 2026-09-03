"""Unit tests for pure solar balancing helpers."""

from homeassistant.components.silla_prism.solar_balance import (
    SOLAR_BALANCE_CHARGING_SURPLUS,
    SOLAR_BALANCE_DISABLED,
    SOLAR_BALANCE_EXTERNAL_PAUSED,
    SOLAR_BALANCE_WAITING_BATTERY_DATA,
    SOLAR_BALANCE_WAITING_DATA,
    SOLAR_BALANCE_WAITING_SOLAR_MODE,
    SURPLUS_SOURCE_PRISM_GRID_BATTERY,
    SURPLUS_SOURCE_SOLAR_HOME_LOAD,
    SolarBalanceState,
    calculate_available_power,
    describe_solar_balance_state,
    get_battery_reserve_power,
    normalize_battery_power,
)


def test_home_load_including_ev_is_corrected() -> None:
    """Test total home load can exclude EV power."""
    result = calculate_available_power(
        ev_power=2600,
        grid_power=0,
        battery_charge_available=0,
        battery_reserve_shortfall=0,
        battery_power_to_exclude=0,
        use_battery_charge=False,
        solar_power=1300,
        home_load_power=3400,
        home_load_includes_ev=True,
    )

    assert result.source == SURPLUS_SOURCE_SOLAR_HOME_LOAD
    assert result.effective_home_load_power == 800
    assert result.available_power == 500


def test_zero_solar_and_battery_discharge_are_not_surplus() -> None:
    """Test zero PV production does not become surplus."""
    result = calculate_available_power(
        ev_power=2660,
        grid_power=-3,
        battery_charge_available=0,
        battery_reserve_shortfall=0,
        battery_power_to_exclude=3607,
        use_battery_charge=True,
        solar_power=0,
        home_load_power=755,
        home_load_includes_ev=False,
    )

    assert result.source == SURPLUS_SOURCE_SOLAR_HOME_LOAD
    assert result.available_power == -755


def test_negative_solar_sensor_is_not_treated_as_production() -> None:
    """Test negative PV readings are clamped out of production."""
    result = calculate_available_power(
        ev_power=0,
        grid_power=0,
        battery_charge_available=0,
        battery_reserve_shortfall=0,
        battery_power_to_exclude=0,
        use_battery_charge=False,
        solar_power=-1200,
        home_load_power=400,
    )

    assert result.source == SURPLUS_SOURCE_SOLAR_HOME_LOAD
    assert result.available_power == -400


def test_fallback_subtracts_grid_import_and_battery_discharge() -> None:
    """Test fallback surplus calculation subtracts import and battery discharge."""
    result = calculate_available_power(
        ev_power=2000,
        grid_power=300,
        battery_charge_available=0,
        battery_reserve_shortfall=0,
        battery_power_to_exclude=600,
        use_battery_charge=False,
    )

    assert result.source == SURPLUS_SOURCE_PRISM_GRID_BATTERY
    assert result.available_power == 1100


def test_battery_reserve_shortfall_reduces_direct_solar_surplus() -> None:
    """Test reserve shortfall keeps power for the home battery."""
    result = calculate_available_power(
        ev_power=1790,
        grid_power=0,
        battery_charge_available=0,
        battery_reserve_shortfall=837,
        battery_power_to_exclude=0,
        use_battery_charge=False,
        solar_power=2652,
        home_load_power=534,
    )

    assert result.source == SURPLUS_SOURCE_SOLAR_HOME_LOAD
    assert result.available_power == 1281


def test_battery_reserve_tracks_soc_thresholds() -> None:
    """Test battery reserve changes with SOC thresholds."""
    assert get_battery_reserve_power(None, 2700, 40, 80, 1500, 1000) == 2700
    assert get_battery_reserve_power(60, 2700, 40, 80, 1500, 1000) == 1500
    assert get_battery_reserve_power(85, 2700, 40, 80, 1500, 1000) == 1000
    assert get_battery_reserve_power(96, 2700, 40, 80, 1500, 1000) == 0


def test_battery_charge_above_reserve_can_become_surplus() -> None:
    """Test excess battery charge power can be reused by EV charging."""
    breakdown = normalize_battery_power(
        battery_power=-2200,
        battery_discharge_positive=True,
        battery_reserve_power=1500,
        use_battery_charge=True,
    )

    assert breakdown.charge_power == 2200
    assert breakdown.discharge_power == 0
    assert breakdown.charge_available_above_reserve == 700
    assert breakdown.power_to_exclude == -700


def test_battery_discharge_positive_setting_is_respected() -> None:
    """Test inverted battery sign convention."""
    breakdown = normalize_battery_power(
        battery_power=-500,
        battery_discharge_positive=False,
        battery_reserve_power=1500,
        use_battery_charge=True,
    )

    assert breakdown.normalized_power == 500
    assert breakdown.discharge_power == 500
    assert breakdown.power_to_exclude == 500


def test_decision_summary_explains_low_surplus_hold() -> None:
    """Test English low-surplus summary."""
    summary = describe_solar_balance_state(
        SolarBalanceState(
            status=SOLAR_BALANCE_CHARGING_SURPLUS,
            available_power=-755,
            target_current=6,
            current_limit_reason="low_surplus_hold_6a",
        )
    )

    assert "Holding 6A" in summary
    assert "-755W" in summary
    assert "Constraint" in summary


def test_decision_summary_uses_italian_when_requested() -> None:
    """Test Italian decision summary."""
    summary = describe_solar_balance_state(
        SolarBalanceState(
            available_power=-755,
            target_current=6,
            current_limit_reason="low_surplus_hold_6a",
        ),
        "it",
    )

    assert "Mantengo 6A" in summary
    assert "surplus calcolato" in summary
    assert "Vincolo" in summary


def test_decision_summary_explains_dry_run() -> None:
    """Test dry-run summary."""
    summary = describe_solar_balance_state(
        SolarBalanceState(
            status=SOLAR_BALANCE_CHARGING_SURPLUS,
            available_power=2800,
            target_current=12,
            current_limit_reason="target_current",
            dry_run=True,
        )
    )

    assert "Dry run" in summary
    assert "would request 12A" in summary
    assert "no MQTT command is sent" in summary


def test_decision_summary_reports_next_stable_surplus_release() -> None:
    """Test stable-surplus countdown summary."""
    summary = describe_solar_balance_state(
        SolarBalanceState(
            target_current=6,
            start_delay_remaining=42,
            current_limit_reason="waiting_stable_surplus",
        )
    )

    assert "Waiting 42s" in summary
    assert "Next release in 42s" in summary


def test_decision_summary_reports_theoretical_pause_target() -> None:
    """Test theoretical target while externally paused."""
    summary = describe_solar_balance_state(
        SolarBalanceState(
            status=SOLAR_BALANCE_EXTERNAL_PAUSED,
            current_limit_reason="external_pause",
            theoretical_target_current=10,
        )
    )

    assert "Theoretical target 10A" in summary


def test_decision_summary_reports_waiting_solar_mode() -> None:
    """Test waiting-for-solar-mode summary."""
    summary = describe_solar_balance_state(
        SolarBalanceState(
            status=SOLAR_BALANCE_WAITING_SOLAR_MODE,
            current_limit_reason="waiting_solar_mode",
            theoretical_target_current=10,
        )
    )

    assert "not in solar mode" in summary


def test_decision_summary_reports_restart_from_minimum() -> None:
    """Test restart summary starts from minimum current."""
    summary = describe_solar_balance_state(
        SolarBalanceState(
            status=SOLAR_BALANCE_CHARGING_SURPLUS,
            target_current=6,
            current_limit_reason="restart_min_current",
            reported_current_limit=32,
        )
    )

    assert "Restarting from 6A" in summary
    assert "old current limit" in summary


def test_decision_summary_handles_disabled_and_waiting_data() -> None:
    """Test simple waiting and disabled summaries."""
    assert (
        describe_solar_balance_state(SolarBalanceState(status=SOLAR_BALANCE_DISABLED))
        == "Solar balancing is disabled."
    )
    assert (
        describe_solar_balance_state(
            SolarBalanceState(status=SOLAR_BALANCE_WAITING_DATA)
        )
        == "Waiting for required sensor data."
    )
    assert (
        describe_solar_balance_state(
            SolarBalanceState(status=SOLAR_BALANCE_WAITING_BATTERY_DATA)
        )
        == "Waiting for battery power data."
    )
