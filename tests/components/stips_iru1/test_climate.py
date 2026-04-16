"""Tests for stips_iru1 climate entities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.stips_iru1 import climate as stips_climate
from homeassistant.components.stips_iru1.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC


@pytest.fixture
def protocol_ac_entity(hass: HomeAssistant) -> stips_climate.StipsIruClimate:
    """Create a protocol AC climate entity for testing."""
    return stips_climate.StipsIruClimate(
        hass=hass,
        device_unique_name="stips-iru1-12345",
        device_name="Test Device",
        device_ip="192.168.1.100",
        device_mac="AA:BB:CC:DD:EE:FF",
        device_online=True,
        remote_id="1",
        friendly_name="Test AC",
        remote_snapshot={"type": "AC", "model": {"protocol": 42}},
    )


@pytest.fixture
def learned_ac_entity(hass: HomeAssistant) -> stips_climate.StipsIruLearnedAcClimate:
    """Create a learned AC climate entity for testing."""
    return stips_climate.StipsIruLearnedAcClimate(
        hass=hass,
        device_unique_name="stips-iru1-67890",
        device_name="Learned Device",
        device_ip="192.168.1.101",
        device_mac="11:22:33:44:55:66",
        device_online=True,
        remote_id="2",
        friendly_name="Learned AC",
        remote_snapshot={
            "type": "LearnedAc",
            "model": {
                "frequency": 38000,
                "signals": [
                    {
                        "mode": "cool",
                        "temperature": 22,
                        "fanSpeed": "medium",
                        "signal": "COOL_22_MED",
                    },
                    {
                        "mode": "heat",
                        "temperature": 20,
                        "fanSpeed": "low",
                        "signal": "HEAT_20_LOW",
                    },
                ],
                "powerOnSignal": "POWER_ON",
                "powerOffSignal": "POWER_OFF",
            },
        },
    )


def _mock_success_post(mock_session: MagicMock, status: int = 200) -> None:
    response = AsyncMock()
    response.status = status
    context = AsyncMock()
    context.__aenter__.return_value = response
    context.__aexit__.return_value = None
    mock_session.post.return_value = context


class TestProtocolAcClimate:
    """Tests for protocol AC climate entity."""

    def test_device_info(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Validate device registry metadata."""
        info = protocol_ac_entity.device_info
        assert info is not None
        assert (DOMAIN, "stips-iru1-12345") in info.identifiers
        assert (CONNECTION_NETWORK_MAC, "AA:BB:CC:DD:EE:FF") in info.connections

    async def test_basic_controls(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Validate user control methods map to _send_update."""
        with patch.object(protocol_ac_entity, "_send_update", new=AsyncMock()) as send:
            await protocol_ac_entity.async_turn_on()
            send.assert_called_with(power=1)

            await protocol_ac_entity.async_turn_off()
            send.assert_called_with(power=0)

            await protocol_ac_entity.async_set_hvac_mode(HVACMode.HEAT)
            assert send.call_args.kwargs["mode"] == 2

            await protocol_ac_entity.async_set_temperature(temperature=50)
            assert send.call_args.kwargs["temp"] == 30

            await protocol_ac_entity.async_set_fan_mode("high")
            assert send.call_args.kwargs["fan"] == 4

            await protocol_ac_entity.async_set_swing_mode("both")
            assert send.call_args.kwargs["swingV"] == 1
            assert send.call_args.kwargs["swingH"] == 1

    async def test_invalid_controls(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Validate validation errors for invalid control inputs."""
        with pytest.raises(HomeAssistantError, match="Temperature is required"):
            await protocol_ac_entity.async_set_temperature()
        with pytest.raises(HomeAssistantError, match="Unsupported fan mode"):
            await protocol_ac_entity.async_set_fan_mode("bad")

    async def test_send_update_error_paths(
        self, protocol_ac_entity: stips_climate.StipsIruClimate, hass: HomeAssistant
    ) -> None:
        """Validate _send_update failure branches."""
        with (
            patch(
                "homeassistant.components.stips_iru1.climate.async_build_control_hosts",
                return_value=([], None),
            ),
            pytest.raises(HomeAssistantError, match="Device host is missing"),
        ):
            await protocol_ac_entity._send_update(power=1)

        no_proto = stips_climate.StipsIruClimate(
            hass=hass,
            device_unique_name="test",
            device_name="test",
            device_ip="",
            device_mac="",
            device_online=True,
            remote_id="1",
            friendly_name="test",
            remote_snapshot={"type": "AC", "model": {}},
        )
        with (
            patch(
                "homeassistant.components.stips_iru1.climate.async_build_control_hosts",
                return_value=(["host"], None),
            ),
            pytest.raises(HomeAssistantError, match="AC protocol is missing"),
        ):
            await no_proto._send_update(power=1)

    async def test_send_update_success_and_timeout(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Validate timeout and success behavior of _send_update."""
        with patch(
            "homeassistant.components.stips_iru1.climate.async_build_control_hosts",
            return_value=(["host1"], "10.0.0.8"),
        ):
            with patch(
                "homeassistant.components.stips_iru1.climate.async_get_clientsession"
            ) as get_session:
                session = MagicMock()
                get_session.return_value = session
                session.post = AsyncMock(side_effect=TimeoutError())

                with pytest.raises(HomeAssistantError, match="Cannot reach IR device"):
                    await protocol_ac_entity._send_update(power=1)

            with patch(
                "homeassistant.components.stips_iru1.climate.async_get_clientsession"
            ) as get_session:
                session = MagicMock()
                get_session.return_value = session
                _mock_success_post(session)
                with patch.object(protocol_ac_entity, "async_write_ha_state"):
                    await protocol_ac_entity._send_update(power=1)

                assert protocol_ac_entity._attr_available is True
                assert protocol_ac_entity._device_ip_live == "10.0.0.8"


class TestLearnedAcClimate:
    """Tests for learned AC climate entity."""

    def test_properties(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Validate baseline properties and derived modes."""
        assert learned_ac_entity.available is True
        assert HVACMode.OFF in learned_ac_entity._attr_hvac_modes
        assert HVACMode.COOL in learned_ac_entity._attr_hvac_modes
        assert "medium" in learned_ac_entity._attr_fan_modes
        assert learned_ac_entity.extra_state_attributes["learned_signal_count"] == 2

    async def test_fan_mode_validation(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Unsupported fan mode should raise immediately."""
        with pytest.raises(HomeAssistantError, match="Unsupported fan mode"):
            await learned_ac_entity.async_set_fan_mode("unsupported")

    async def test_send_state_paths(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Validate matching signal, fallback signal, and no-match errors."""
        with patch.object(learned_ac_entity, "_post_signal", new=AsyncMock()) as post:
            await learned_ac_entity._send_state(
                power=1,
                hvac_mode=HVACMode.COOL,
                temp=22,
                fan="medium",
            )
            post.assert_called_once_with("COOL_22_MED")

        learned_ac_entity._power_on_signal = "POWER_ON"
        with patch.object(learned_ac_entity, "_post_signal", new=AsyncMock()) as post:
            await learned_ac_entity._send_state(power=1, hvac_mode=HVACMode.FAN_ONLY)
            post.assert_called_once_with("POWER_ON")

        learned_ac_entity._power_on_signal = None
        with pytest.raises(HomeAssistantError, match="No learned AC signal matches"):
            await learned_ac_entity._send_state(power=1, hvac_mode=HVACMode.FAN_ONLY)

    async def test_post_signal_hosts_and_fallback(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Validate host missing, timeout, and fallback-to-second-host behavior."""
        with (
            patch(
                "homeassistant.components.stips_iru1.climate.async_build_control_hosts",
                return_value=([], None),
            ),
            pytest.raises(HomeAssistantError, match="Device host is missing"),
        ):
            await learned_ac_entity._post_signal("SIG")

        with (
            patch(
                "homeassistant.components.stips_iru1.climate.async_build_control_hosts",
                return_value=(["host1"], None),
            ),
            patch(
                "homeassistant.components.stips_iru1.climate.async_get_clientsession"
            ) as get_session,
        ):
            session = MagicMock()
            get_session.return_value = session
            session.post = AsyncMock(side_effect=TimeoutError())

            with (
                patch.object(learned_ac_entity, "async_write_ha_state"),
                pytest.raises(HomeAssistantError, match="Cannot reach IR device"),
            ):
                await learned_ac_entity._post_signal("SIG")

        with (
            patch(
                "homeassistant.components.stips_iru1.climate.async_build_control_hosts",
                return_value=(["host1", "host2"], None),
            ),
            patch(
                "homeassistant.components.stips_iru1.climate.async_get_clientsession"
            ) as get_session,
        ):
            session = MagicMock()
            get_session.return_value = session

            response = AsyncMock()
            response.status = 200
            context = AsyncMock()
            context.__aenter__.return_value = response
            context.__aexit__.return_value = None
            session.post.side_effect = [TimeoutError(), context]

            with patch.object(learned_ac_entity, "async_write_ha_state"):
                await learned_ac_entity._post_signal("SIG")

            assert session.post.call_count == 2
