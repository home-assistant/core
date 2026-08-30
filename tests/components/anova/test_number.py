"""Test the Anova numbers."""

from unittest.mock import AsyncMock

from anova_wifi import CommandFailure
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import async_init_integration, get_device


@pytest.mark.usefixtures("anova_api")
async def test_numbers_seeded_from_device_state(hass: HomeAssistant) -> None:
    """Test the numbers are seeded from the device's own last-reported job values."""
    await async_init_integration(hass)
    assert (
        hass.states.get("number.anova_precision_cooker_target_temperature").state
        == "54.72"
    )
    assert hass.states.get("number.anova_precision_cooker_timer").state == "0.0"


@pytest.mark.usefixtures("anova_api_cooking")
async def test_numbers_reflect_the_live_job_when_already_cooking_on_add(
    hass: HomeAssistant,
) -> None:
    """Test the numbers show the live job's values, not the idle seed, on setup.

    A restart during a cook must not show a stale target/timer until the next
    websocket push - see AnovaTargetTemperatureNumber/AnovaTimerNumber's
    async_added_to_hass.
    """
    await async_init_integration(hass)
    assert (
        hass.states.get("number.anova_precision_cooker_target_temperature").state
        == "60"
    )
    assert hass.states.get("number.anova_precision_cooker_timer").state == "30.0"


@pytest.mark.usefixtures("anova_api")
async def test_pending_value_survives_restart_while_device_is_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test a locally-held value is restored even if the device was offline at shutdown.

    RestoreNumber's extra data reflects the last value this entity held
    regardless of availability, so a prior state of STATE_UNAVAILABLE must
    not be treated the same as never having a value at all.
    """
    entry = await async_init_integration(hass)
    coordinator = entry.runtime_data.coordinators[0]

    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.anova_precision_cooker_target_temperature",
            "value": 65,
        },
        blocking=True,
    )

    coordinator.anova_device.last_update_received_at = (
        dt_util.utcnow() - DEVICE_STALE_THRESHOLD - timedelta(seconds=1)
    )
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RECONNECT_RETRY_DELAY + 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        hass.states.get("number.anova_precision_cooker_target_temperature").state
        == "unavailable"
    )

    await async_mock_restore_state_shutdown_restart(hass)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    new_coordinator = entry.runtime_data.coordinators[0]
    assert new_coordinator.pending_target_temperature == 65


@pytest.mark.usefixtures("anova_api_unsupported_device_type")
async def test_no_numbers_for_unsupported_device_type(hass: HomeAssistant) -> None:
    """Test no number entities are created for a device type with no command capabilities."""
    await async_init_integration(hass)
    assert hass.states.async_all("number") == []


@pytest.mark.usefixtures("anova_api")
async def test_setting_target_temperature_while_idle_is_local_only(
    hass: HomeAssistant,
) -> None:
    """Test setting the target temperature while idle just stores it locally."""
    entry = await async_init_integration(hass)
    device = get_device(entry)
    device.update_running_cook = AsyncMock()

    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.anova_precision_cooker_target_temperature",
            "value": 60,
        },
        blocking=True,
    )

    assert (
        hass.states.get("number.anova_precision_cooker_target_temperature").state
        == "60.0"
    )
    device.update_running_cook.assert_not_called()


@pytest.mark.usefixtures("anova_api")
async def test_setting_timer_to_zero_while_idle_is_allowed(
    hass: HomeAssistant,
) -> None:
    """Test the timer accepts 0 minutes, the protocol's supported no-timer value."""
    await async_init_integration(hass)

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.anova_precision_cooker_timer", "value": 0},
        blocking=True,
    )

    assert hass.states.get("number.anova_precision_cooker_timer").state == "0.0"


@pytest.mark.usefixtures("anova_api_cooking")
@pytest.mark.parametrize(
    ("entity_id", "value", "expected_kwargs"),
    [
        pytest.param(
            "number.anova_precision_cooker_target_temperature",
            65,
            {"target_temperature": 65.0, "temperature_unit": "C"},
            id="target_temperature",
        ),
        pytest.param(
            "number.anova_precision_cooker_timer",
            15,
            {"cook_time_seconds": 900},
            id="timer_in_minutes",
        ),
    ],
)
async def test_setting_while_cooking_updates_the_running_cook(
    hass: HomeAssistant,
    entity_id: str,
    value: float,
    expected_kwargs: dict[str, object],
) -> None:
    """Test setting a number while cooking calls update_running_cook."""
    entry = await async_init_integration(hass)
    device = get_device(entry)
    assert device.is_cooking is True
    device.update_running_cook = AsyncMock()

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": value},
        blocking=True,
    )

    device.update_running_cook.assert_awaited_once_with(**expected_kwargs)


@pytest.mark.usefixtures("anova_api_cooking")
async def test_setting_target_temperature_while_cooking_persists_as_pending(
    hass: HomeAssistant,
) -> None:
    """Test a live target-temperature change is remembered for the next cook.

    Otherwise stopping the cook would make the entity revert to the pre-cook
    target instead of the value just set while cooking.
    """
    entry = await async_init_integration(hass)
    device = get_device(entry)
    device.update_running_cook = AsyncMock()

    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.anova_precision_cooker_target_temperature",
            "value": 65,
        },
        blocking=True,
    )

    coordinator = entry.runtime_data.coordinators[0]
    assert coordinator.pending_target_temperature == 65


@pytest.mark.usefixtures("anova_api_cooking")
async def test_setting_timer_while_cooking_persists_as_pending(
    hass: HomeAssistant,
) -> None:
    """Test a live timer change is remembered, in seconds, for the next cook."""
    entry = await async_init_integration(hass)
    device = get_device(entry)
    device.update_running_cook = AsyncMock()

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.anova_precision_cooker_timer", "value": 15},
        blocking=True,
    )

    coordinator = entry.runtime_data.coordinators[0]
    assert coordinator.pending_cook_time_seconds == 900


@pytest.mark.usefixtures("anova_api_cooking")
async def test_setting_target_temperature_failure_raises(hass: HomeAssistant) -> None:
    """Test a CommandFailure while cooking surfaces as HomeAssistantError."""
    entry = await async_init_integration(hass)
    device = get_device(entry)
    device.update_running_cook = AsyncMock(side_effect=CommandFailure("boom"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "number",
            "set_value",
            {
                "entity_id": "number.anova_precision_cooker_target_temperature",
                "value": 65,
            },
            blocking=True,
        )
