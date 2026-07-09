"""The tests for the evohome coordinator."""

from datetime import timedelta
import logging
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.evohome import EvoData
from homeassistant.components.evohome.const import CONF_LOCATION_IDX, DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component

from .conftest import mock_make_request, mock_post_request

from tests.common import async_fire_time_changed


@pytest.mark.parametrize("install", ["minimal"])
@pytest.mark.usefixtures("evohome")
async def test_setup_platform(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities and their states after setup of evohome."""

    evo_data: EvoData = hass.data.get(DOMAIN)  # type: ignore[assignment]
    update_interval: timedelta = evo_data.coordinator.update_interval  # type: ignore[assignment]

    # confirm initial state after coordinator.async_first_refresh()...
    state = hass.states.get("climate.my_home")
    assert state is not None and state.state != STATE_UNAVAILABLE

    with patch(
        "homeassistant.components.evohome.coordinator.EvoDataUpdateCoordinator._async_update_data",
        side_effect=UpdateFailed,
    ):
        freezer.tick(update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # confirm appropriate response to loss of state...
    state = hass.states.get("climate.my_home")
    assert state is not None and state.state == STATE_UNAVAILABLE

    freezer.tick(update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # if coordinator is working, the state will be restored
    state = hass.states.get("climate.my_home")
    assert state is not None and state.state != STATE_UNAVAILABLE


async def test_setup_platform_no_gateway_at_location(
    hass: HomeAssistant,
    config: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup fails cleanly when location_idx points at a gateway-less location.

    sys_004's "RFG100 (OBF5)" location (index 3) has no gateways at all, a real edge
    case seen in a genuine multi-location account.
    """

    config[CONF_LOCATION_IDX] = 3

    with (
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            mock_post_request("sys_004"),
        ),
        patch("_evohome.auth.AbstractAuth._make_request", mock_make_request("sys_004")),
        caplog.at_level(logging.ERROR),
    ):
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})

    assert result is False

    assert any(
        "no gateway/system available" in message
        for _, _, message in caplog.record_tuples
    )
