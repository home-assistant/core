"""The test for the ecobee thermostat switch module."""

import copy
from datetime import timedelta
import logging
from unittest import mock
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from pytest_homeassistant.common import mock_restore_cache_with_extra_data

from homeassistant.components.ecobee.switch import (
    DATE_FORMAT,
    EcobeeAuxHeatOnlyExtraStoredData,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from . import GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP
from .common import setup_platform

VENTILATOR_20MIN_ID = "switch.ecobee_ventilator_20m_timer"
THERMOSTAT_ID = 0
THERMOSTAT_TIMEZONE = ZoneInfo(
    GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP["location"]["timeZone"]
)


@pytest.fixture(name="data")
def data_fixture():
    """Set up data mock."""
    data = mock.Mock()
    data.return_value = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    return data


async def test_ventilator_20min_attributes(hass: HomeAssistant) -> None:
    """Test the ventilator switch on home attributes are correct."""
    await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(VENTILATOR_20MIN_ID)
    assert state.state == "off"


async def test_ventilator_20min_when_on(hass: HomeAssistant, data) -> None:
    """Test the ventilator switch goes on."""

    data.return_value["settings"]["ventilatorOffDateTime"] = (
        dt_util.now(THERMOSTAT_TIMEZONE) + timedelta(days=1)
    ).strftime(DATE_FORMAT)
    with mock.patch("pyecobee.Ecobee.get_thermostat", data):
        await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(VENTILATOR_20MIN_ID)
    assert state.state == "on"

    data.reset_mock()


async def test_ventilator_20min_when_off(hass: HomeAssistant, data) -> None:
    """Test the ventilator switch goes on."""

    data.return_value["settings"]["ventilatorOffDateTime"] = (
        dt_util.now(THERMOSTAT_TIMEZONE) - timedelta(days=1)
    ).strftime(DATE_FORMAT)
    with mock.patch("pyecobee.Ecobee.get_thermostat", data):
        await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(VENTILATOR_20MIN_ID)
    assert state.state == "off"

    data.reset_mock()


async def test_ventilator_20min_when_empty(hass: HomeAssistant, data) -> None:
    """Test the ventilator switch goes on."""

    data.return_value["settings"]["ventilatorOffDateTime"] = ""
    with mock.patch("pyecobee.Ecobee.get_thermostat", data):
        await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get(VENTILATOR_20MIN_ID)
    assert state.state == "off"

    data.reset_mock()


async def test_turn_on_20min_ventilator(hass: HomeAssistant) -> None:
    """Test the switch 20 min timer (On)."""

    with patch(
        "homeassistant.components.ecobee.Ecobee.set_ventilator_timer"
    ) as mock_set_20min_ventilator:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_ON,
            {TargetKey.ENTITY_ID: VENTILATOR_20MIN_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_20min_ventilator.assert_called_once_with(THERMOSTAT_ID, True)


async def test_turn_off_20min_ventilator(hass: HomeAssistant) -> None:
    """Test the switch 20 min timer (off)."""

    with patch(
        "homeassistant.components.ecobee.Ecobee.set_ventilator_timer"
    ) as mock_set_20min_ventilator:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: VENTILATOR_20MIN_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_20min_ventilator.assert_called_once_with(THERMOSTAT_ID, False)


DEVICE_ID = "switch.ecobee2_auxiliary_heat_only"
SECOND_THERMOSTAT_ID = "switch.ecobee_auxiliary_heat_only"


async def test_aux_heat_only_turn_on(hass: HomeAssistant) -> None:
    """Test the switch can be turned on."""
    with patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_on:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_ON,
            {TargetKey.ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        mock_turn_on.assert_called_once_with(1, "auxHeatOnly")


async def test_aux_heat_only_turn_on_refresh_turn_off(hass: HomeAssistant) -> None:
    """Test the prior mode survives the refresh following turn on."""
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    with (
        patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_set_hvac_mode,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)
        entity = hass.data[SWITCH_DOMAIN].get_entity(SECOND_THERMOSTAT_ID)
        assert entity is not None
        assert entity.extra_restore_state_data is None
        # Call directly to inspect the saved mode before polling the sync entity.
        entity.turn_on()
        assert entity.update_without_throttle is True

        with patch.object(
            entity.data, "update", wraps=entity.data.update
        ) as mock_update:
            thermostat["settings"]["hvacMode"] = "auxHeatOnly"
            await entity.async_update()

        assert mock.call(no_throttle=True) in mock_update.call_args_list
        assert entity.update_without_throttle is False
        assert entity.extra_restore_state_data.hvac_mode == "auto"
        thermostat["settings"]["hvacMode"] = "auxHeatOnly"
        entity.turn_off()
        mock_set_hvac_mode.assert_has_calls(
            [mock.call(1, "auxHeatOnly"), mock.call(1, "auto")]
        )
        assert entity.extra_restore_state_data.hvac_mode == "auto"


async def test_aux_heat_only_turn_on_when_on(hass: HomeAssistant) -> None:
    """Test turning on the switch again doesn't overwrite the saved HVAC mode."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(SECOND_THERMOSTAT_ID, "on"),
                {"hvac_mode_before_aux_heat": "heat"},
            )
        ],
    )
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    thermostat["settings"]["hvacMode"] = "auxHeatOnly"
    with (
        patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_on,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_ON,
            {TargetKey.ENTITY_ID: SECOND_THERMOSTAT_ID},
            blocking=True,
        )
        mock_turn_on.assert_not_called()


async def test_aux_heat_only_turn_off(hass: HomeAssistant) -> None:
    """Test turning off aux heat without a saved mode restores to auto."""
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    thermostat["settings"]["hvacMode"] = "auxHeatOnly"
    with (
        patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_off,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: SECOND_THERMOSTAT_ID},
            blocking=True,
        )
        mock_turn_off.assert_called_once_with(1, "auto")


async def test_aux_heat_only_turn_off_when_off(hass: HomeAssistant) -> None:
    """Test turning off an already-off switch does not change HVAC mode."""
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    with (
        patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_off,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)
        entity = hass.data[SWITCH_DOMAIN].get_entity(SECOND_THERMOSTAT_ID)
        assert entity is not None

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: SECOND_THERMOSTAT_ID},
            blocking=True,
        )
        mock_turn_off.assert_not_called()


async def test_aux_heat_only_turn_off_when_live_aux_but_no_restore_mode(
    hass: HomeAssistant,
) -> None:
    """Test turning off externally enabled aux heat falls back to auto."""
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    thermostat["settings"]["hvacMode"] = "auxHeatOnly"
    with (
        patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_off,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: SECOND_THERMOSTAT_ID},
            blocking=True,
        )
        mock_turn_off.assert_called_once_with(1, "auto")


async def test_aux_heat_only_turn_off_after_restart(hass: HomeAssistant) -> None:
    """Test the switch restores the prior mode after a Home Assistant restart."""
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    thermostat["settings"]["hvacMode"] = "auxHeatOnly"
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(SECOND_THERMOSTAT_ID, "on"),
                {"hvac_mode_before_aux_heat": "heat"},
            )
        ],
    )
    with (
        patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_off,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: SECOND_THERMOSTAT_ID},
            blocking=True,
        )
        mock_turn_off.assert_called_once_with(1, "heat")


@pytest.mark.parametrize(
    ("stored_state", "live_mode", "expected_restore"),
    [
        pytest.param("on", "heat", None, id="stale-on-live-heat"),
        pytest.param("off", "auxHeatOnly", "heat", id="stale-off-live-aux"),
        pytest.param("unavailable", "auxHeatOnly", "heat", id="unavailable-live-aux"),
    ],
)
async def test_aux_heat_only_restores_from_live_mode(
    hass: HomeAssistant,
    stored_state: str,
    live_mode: str,
    expected_restore: str | None,
) -> None:
    """Test restoration uses live thermostat mode instead of the saved state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(SECOND_THERMOSTAT_ID, stored_state),
                {"hvac_mode_before_aux_heat": "heat"},
            )
        ],
    )
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    thermostat["settings"]["hvacMode"] = live_mode
    with (
        patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_set_hvac_mode,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)
        entity = hass.data[SWITCH_DOMAIN].get_entity(SECOND_THERMOSTAT_ID)
        assert entity is not None
        assert entity.is_on is (live_mode == "auxHeatOnly")
        mock_set_hvac_mode.assert_not_called()
        if expected_restore is None:
            assert entity.extra_restore_state_data is None
        else:
            assert entity.extra_restore_state_data.hvac_mode == expected_restore


async def test_aux_heat_only_turn_off_with_invalid_restore_mode(
    hass: HomeAssistant,
) -> None:
    """Test turning off with an unknown HVAC mode restores to auto."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(SECOND_THERMOSTAT_ID, "on"),
                {"hvac_mode_before_aux_heat": "invalid"},
            )
        ],
    )
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    thermostat["settings"]["hvacMode"] = "auxHeatOnly"
    with (
        patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_off,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: SECOND_THERMOSTAT_ID},
            blocking=True,
        )
        mock_turn_off.assert_called_once_with(1, "auto")


async def test_aux_heat_only_turn_off_without_restore_data(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test turning off aux heat without restore data falls back to auto."""
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    thermostat["settings"]["hvacMode"] = "auxHeatOnly"
    with (
        patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_turn_off,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)
        with caplog.at_level(
            logging.WARNING, logger="homeassistant.components.ecobee.switch"
        ):
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SwitchService.TURN_OFF,
                {TargetKey.ENTITY_ID: SECOND_THERMOSTAT_ID},
                blocking=True,
            )
        mock_turn_off.assert_called_once_with(1, "auto")
        assert "falling back to auto" in caplog.text


@pytest.mark.parametrize("invalid_mode", [[], {}], ids=["list", "dict"])
def test_aux_heat_extra_data_rejects_unhashable_mode(
    invalid_mode: list[object] | dict[object, object],
) -> None:
    """Test corrupt unhashable modes are rejected safely."""
    assert (
        EcobeeAuxHeatOnlyExtraStoredData.from_dict(
            {"hvac_mode_before_aux_heat": invalid_mode}
        )
        is None
    )


async def test_aux_heat_only_clears_previous_mode_when_changed_remotely(
    hass: HomeAssistant,
) -> None:
    """Test an external HVAC mode change clears the saved auxiliary heat mode."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(SECOND_THERMOSTAT_ID, "on"),
                {"hvac_mode_before_aux_heat": "heat"},
            )
        ],
    )
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    thermostat["settings"]["hvacMode"] = "auxHeatOnly"
    with (
        patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_set_hvac_mode,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)
        entity = hass.data[SWITCH_DOMAIN].get_entity(SECOND_THERMOSTAT_ID)
        assert entity is not None
        assert entity.extra_restore_state_data.hvac_mode == "heat"

        async def apply_external_mode(no_throttle: bool = False) -> None:
            """Emulate a successful refresh after an external mode change."""
            thermostat["settings"]["hvacMode"] = "cool"

        with patch.object(entity.data, "update", side_effect=apply_external_mode):
            await entity.async_update()
        assert entity.extra_restore_state_data is None
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: SECOND_THERMOSTAT_ID},
            blocking=True,
        )

        mock_set_hvac_mode.assert_not_called()


async def test_aux_heat_only_turn_on_keeps_restore_mode_when_refresh_fails(
    hass: HomeAssistant,
) -> None:
    """Test a failed refresh doesn't clear the restore mode."""
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    with (
        patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_set_hvac_mode,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)
        entity = hass.data[SWITCH_DOMAIN].get_entity(SECOND_THERMOSTAT_ID)
        assert entity is not None
        entity.turn_on()
        thermostat["settings"]["hvacMode"] = "auxHeatOnly"

        with patch.object(entity.data, "update", new_callable=AsyncMock):
            await entity.async_update()

        assert entity.extra_restore_state_data.hvac_mode == "auto"
        entity.turn_off()
        mock_set_hvac_mode.assert_has_calls(
            [mock.call(1, "auxHeatOnly"), mock.call(1, "auto")]
        )


async def test_aux_heat_only_clears_restore_mode_after_external_mode_change(
    hass: HomeAssistant,
) -> None:
    """Test a confirmed external mode change clears the saved restore mode."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(SECOND_THERMOSTAT_ID, "on"),
                {"hvac_mode_before_aux_heat": "heat"},
            )
        ],
    )
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    thermostat["settings"]["hvacMode"] = "auxHeatOnly"
    with patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat):
        await setup_platform(hass, SWITCH_DOMAIN)
        entity = hass.data[SWITCH_DOMAIN].get_entity(SECOND_THERMOSTAT_ID)
        assert entity is not None
        with patch.object(entity.data, "update", new_callable=AsyncMock) as mock_update:

            async def apply_external_mode(no_throttle: bool = False) -> None:
                """Emulate an API refresh with an external thermostat mode change."""
                thermostat["settings"]["hvacMode"] = "cool"

            mock_update.side_effect = apply_external_mode
            await entity.async_update()
        assert entity.extra_restore_state_data is None


async def test_aux_heat_only_keeps_restore_mode_when_refresh_fails(
    hass: HomeAssistant,
) -> None:
    """Test a failed refresh doesn't clear the saved prior mode."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(SECOND_THERMOSTAT_ID, "on"),
                {"hvac_mode_before_aux_heat": "heat"},
            )
        ],
    )
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    thermostat["settings"]["hvacMode"] = "auxHeatOnly"
    with patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat):
        await setup_platform(hass, SWITCH_DOMAIN)
        entity = hass.data[SWITCH_DOMAIN].get_entity(SECOND_THERMOSTAT_ID)
        assert entity is not None
        assert entity.extra_restore_state_data.hvac_mode == "heat"

        with patch.object(entity.data, "update", new_callable=AsyncMock):
            await entity.async_update()
        assert entity.extra_restore_state_data.hvac_mode == "heat"


@pytest.mark.parametrize("invalid_mode", [None, 1], ids=["none", "integer"])
def test_aux_heat_extra_data_rejects_non_string_mode(invalid_mode: object) -> None:
    """Test non-string modes are rejected safely."""
    assert (
        EcobeeAuxHeatOnlyExtraStoredData.from_dict(
            {"hvac_mode_before_aux_heat": invalid_mode}
        )
        is None
    )


async def test_aux_heat_only_turn_on_after_rapid_turn_off(hass: HomeAssistant) -> None:
    """Test a rapid re-enable keeps the original mode as the restore target."""
    thermostat = copy.deepcopy(GENERIC_THERMOSTAT_INFO_WITH_HEATPUMP)
    with (
        patch("pyecobee.Ecobee.get_thermostat", return_value=thermostat),
        patch("pyecobee.Ecobee.set_hvac_mode") as mock_set_hvac_mode,
    ):
        await setup_platform(hass, SWITCH_DOMAIN)
        entity = hass.data[SWITCH_DOMAIN].get_entity(SECOND_THERMOSTAT_ID)
        assert entity is not None
        entity.turn_on()
        thermostat["settings"]["hvacMode"] = "auxHeatOnly"
        entity.turn_off()
        thermostat["settings"]["hvacMode"] = "auto"
        entity.turn_on()
        thermostat["settings"]["hvacMode"] = "auxHeatOnly"
        entity.turn_off()

        mock_set_hvac_mode.assert_has_calls(
            [
                mock.call(1, "auxHeatOnly"),
                mock.call(1, "auto"),
                mock.call(1, "auxHeatOnly"),
                mock.call(1, "auto"),
            ]
        )
