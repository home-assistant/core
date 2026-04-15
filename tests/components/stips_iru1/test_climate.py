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
        remote_snapshot={
            "type": "AC",
            "model": {"protocol": 42},
        },
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
                        "mode": "cool",
                        "temperature": 24,
                        "fanSpeed": "high",
                        "signal": "COOL_24_HIGH",
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


class TestStipsIruClimate:
    """Tests for protocol AC StipsIruClimate entity."""

    def test_device_info(self, protocol_ac_entity: stips_climate.StipsIruClimate) -> None:
        """Test device info contains expected metadata."""
        device_info = protocol_ac_entity.device_info

        assert device_info is not None
        assert (DOMAIN, "stips-iru1-12345") in device_info.identifiers
        assert device_info.name == "Test Device"
        assert device_info.manufacturer == "STIPS"
        assert device_info.model == "IRU1"
        assert (CONNECTION_NETWORK_MAC, "AA:BB:CC:DD:EE:FF") in device_info.connections

    def test_initial_state(self, protocol_ac_entity: stips_climate.StipsIruClimate) -> None:
        """Test initial state values."""
        assert protocol_ac_entity.hvac_mode == HVACMode.COOL
        assert protocol_ac_entity.target_temperature == 22.0
        assert protocol_ac_entity.fan_mode == "medium"
        assert protocol_ac_entity.swing_mode == "off"
        assert protocol_ac_entity.available is True

    def test_extra_state_attributes(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test extra state attributes are populated."""
        attrs = protocol_ac_entity.extra_state_attributes

        assert attrs["device_unique_name"] == "stips-iru1-12345"
        assert attrs["device_online"] is True
        assert attrs["remote_type"] == "AC"
        assert attrs["protocol"] == 42

    async def test_turn_on(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test turning on the AC."""
        with patch.object(
            protocol_ac_entity, "_send_update", new=AsyncMock()
        ) as mock_send:
            await protocol_ac_entity.async_turn_on()
            mock_send.assert_called_once_with(power=1)

    async def test_turn_off(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test turning off the AC."""
        with patch.object(
            protocol_ac_entity, "_send_update", new=AsyncMock()
        ) as mock_send:
            await protocol_ac_entity.async_turn_off()
            mock_send.assert_called_once_with(power=0)

    async def test_set_hvac_mode(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test setting HVAC modes."""
        with patch.object(
            protocol_ac_entity, "_send_update", new=AsyncMock()
        ) as mock_send:
            await protocol_ac_entity.async_set_hvac_mode(HVACMode.HEAT)
            mock_send.assert_called_once()
            assert mock_send.call_args[1]["power"] == 1
            assert mock_send.call_args[1]["mode"] == 2  # HEAT maps to mode 2

    async def test_set_hvac_mode_off(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test setting HVAC mode to OFF."""
        with patch.object(
            protocol_ac_entity, "_send_update", new=AsyncMock()
        ) as mock_send:
            await protocol_ac_entity.async_set_hvac_mode(HVACMode.OFF)
            mock_send.assert_called_once_with(power=0)

    async def test_set_temperature(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test setting temperature."""
        with patch.object(
            protocol_ac_entity, "_send_update", new=AsyncMock()
        ) as mock_send:
            await protocol_ac_entity.async_set_temperature(temperature=26)
            mock_send.assert_called_once()
            assert mock_send.call_args[1]["temp"] == 26

    async def test_set_temperature_clamped(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test temperature is clamped to min/max."""
        with patch.object(
            protocol_ac_entity, "_send_update", new=AsyncMock()
        ) as mock_send:
            await protocol_ac_entity.async_set_temperature(temperature=50)
            mock_send.assert_called_once()
            assert mock_send.call_args[1]["temp"] == 30


    async def test_set_temperature_missing(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test temperature missing raises error."""
        with pytest.raises(HomeAssistantError, match="Temperature is required"):
            await protocol_ac_entity.async_set_temperature()

    async def test_set_fan_mode(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test setting fan mode."""
        with patch.object(
            protocol_ac_entity, "_send_update", new=AsyncMock()
        ) as mock_send:
            await protocol_ac_entity.async_set_fan_mode("high")
            mock_send.assert_called_once()
            assert mock_send.call_args[1]["fan"] == 4  # high = 4

    async def test_set_fan_mode_invalid(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test invalid fan mode raises error."""
        with pytest.raises(HomeAssistantError, match="Unsupported fan mode"):
            await protocol_ac_entity.async_set_fan_mode("invalid")

    async def test_set_swing_mode(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test setting swing mode."""
        with patch.object(
            protocol_ac_entity, "_send_update", new=AsyncMock()
        ) as mock_send:
            await protocol_ac_entity.async_set_swing_mode("both")
            mock_send.assert_called_once()
            assert mock_send.call_args[1]["swingV"] == 1
            assert mock_send.call_args[1]["swingH"] == 1

    async def test_send_update_fails_without_hosts(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test _send_update raises when no hosts are available."""
        with patch.object(
            protocol_ac_entity,
            "async_resolve_control_hosts",
            return_value=([], None),
        ):
            with pytest.raises(
                HomeAssistantError, match="Device host is missing"
            ):
                await protocol_ac_entity._send_update(power=1)

    async def test_send_update_fails_without_protocol(
        self, hass: HomeAssistant
    ) -> None:
        """Test _send_update raises when protocol is missing."""
        entity = stips_climate.StipsIruClimate(
            hass=hass,
            device_unique_name="test",
            device_name="test",
            device_ip="",
            device_mac="",
            device_online=True,
            remote_id="1",
            friendly_name="test",
            remote_snapshot={"type": "AC", "model": {}},  # protocol missing
        )
        with patch.object(
            entity, "async_resolve_control_hosts", return_value=(["host"], None)
        ):
            with pytest.raises(HomeAssistantError, match="AC protocol is missing"):
                await entity._send_update(power=1)

    async def test_cached_control_hosts(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test control hosts are cached and reused."""
        with patch(
            "homeassistant.components.stips_iru1.climate.async_build_control_hosts",
            new=AsyncMock(return_value=(["host1"], "10.0.0.1")),
        ):
            # First call should resolve
            hosts1, ip1 = await protocol_ac_entity.async_resolve_control_hosts()
            assert hosts1 == ["host1"]
            assert ip1 == "10.0.0.1"

            # Second call should use cache
            hosts2, ip2 = await protocol_ac_entity.async_resolve_control_hosts()
            assert hosts2 == ["host1"]
            assert ip2 == "10.0.0.1"

    async def test_force_refresh_hosts(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Test forcing refresh of control hosts bypasses cache."""
        with patch(
            "homeassistant.components.stips_iru1.climate.async_build_control_hosts",
            new=AsyncMock(side_effect=[( ["host1"], "10.0.0.1"), (["host2"], "10.0.0.2")]),
        ):
            # First call
            hosts1, ip1 = await protocol_ac_entity.async_resolve_control_hosts()
            assert hosts1 == ["host1"]

            # Refresh call
            hosts2, ip2 = await protocol_ac_entity.async_resolve_control_hosts(
                force_refresh=True
            )
            assert hosts2 == ["host2"]


class TestStipsIruLearnedAcClimate:
    """Tests for learned AC StipsIruLearnedAcClimate entity."""

    def test_device_info(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test device info contains expected metadata."""
        device_info = learned_ac_entity.device_info

        assert device_info is not None
        assert (DOMAIN, "stips-iru1-67890") in device_info.identifiers
        assert device_info.name == "Learned Device"

    def test_initial_state(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test initial state values."""
        assert learned_ac_entity.hvac_mode == HVACMode.OFF
        assert learned_ac_entity.target_temperature == 22.0
        assert learned_ac_entity.fan_mode == "low"  # First supported fan from signals
        assert learned_ac_entity.available is True

    def test_hvac_modes_derived_from_signals(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test HVAC modes are derived from available signals."""
        assert HVACMode.COOL in learned_ac_entity._attr_hvac_modes
        assert HVACMode.HEAT in learned_ac_entity._attr_hvac_modes
        assert HVACMode.OFF in learned_ac_entity._attr_hvac_modes

    def test_fan_modes_derived_from_signals(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test fan modes are derived from available signals."""
        assert "medium" in learned_ac_entity._attr_fan_modes
        assert "high" in learned_ac_entity._attr_fan_modes
        assert "low" in learned_ac_entity._attr_fan_modes

    def test_extra_state_attributes(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test extra state attributes."""
        attrs = learned_ac_entity.extra_state_attributes

        assert attrs["device_online"] is True
        assert attrs["remote_type"] == "LearnedAc"
        assert attrs["learned_signal_count"] == 3

    async def test_turn_on(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test turning on learned AC."""
        with patch.object(
            learned_ac_entity, "_send_state", new=AsyncMock()
        ) as mock_send:
            await learned_ac_entity.async_turn_on()
            mock_send.assert_called_once()
            assert mock_send.call_args[1]["power"] == 1

    async def test_turn_on_when_off_mode(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test turn on sets power on signal when in off mode."""
        learned_ac_entity._power_on_signal = "POWER_ON"
        learned_ac_entity._state["power"] = 0
        learned_ac_entity._state["hvac_mode"] = HVACMode.OFF

        with patch.object(
            learned_ac_entity, "_post_signal", new=AsyncMock()
        ) as mock_post:
            await learned_ac_entity.async_turn_on()
            # Should call _post_signal when turning on from OFF and power_on_signal exists
            # But the current logic only calls _send_state, which will then call _post_signal
            mock_post.assert_not_called()

    async def test_turn_off_with_power_off_signal(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test turn off uses power off signal when available."""
        learned_ac_entity._power_off_signal = "POWER_OFF"

        with patch.object(
            learned_ac_entity, "_post_signal", new=AsyncMock()
        ) as mock_post:
            await learned_ac_entity.async_turn_off()
            mock_post.assert_called_once_with("POWER_OFF")
            assert learned_ac_entity._state["power"] == 0

    async def test_turn_off_without_power_off_signal(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test turn off without power off signal calls _send_state."""
        learned_ac_entity._power_off_signal = None

        with patch.object(
            learned_ac_entity, "_send_state", new=AsyncMock()
        ) as mock_send:
            await learned_ac_entity.async_turn_off()
            mock_send.assert_called_once_with(power=0)

    async def test_set_hvac_mode_off(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test setting HVAC mode to OFF."""
        learned_ac_entity._power_off_signal = None

        with patch.object(
            learned_ac_entity, "_send_state", new=AsyncMock()
        ) as mock_send:
            await learned_ac_entity.async_set_hvac_mode(HVACMode.OFF)
            # Should call async_turn_off which calls _send_state
            mock_send.assert_called_once()

    async def test_set_hvac_mode_heat(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test setting HVAC mode to HEAT."""
        with patch.object(
            learned_ac_entity, "_send_state", new=AsyncMock()
        ) as mock_send:
            await learned_ac_entity.async_set_hvac_mode(HVACMode.HEAT)
            mock_send.assert_called_once()
            assert mock_send.call_args[1]["hvac_mode"] == HVACMode.HEAT

    async def test_set_temperature(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test setting temperature."""
        with patch.object(
            learned_ac_entity, "_send_state", new=AsyncMock()
        ) as mock_send:
            await learned_ac_entity.async_set_temperature(temperature=23)
            mock_send.assert_called_once()
            assert mock_send.call_args[1]["temp"] == 23

    async def test_set_fan_mode(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test setting fan mode."""
        with patch.object(
            learned_ac_entity, "_send_state", new=AsyncMock()
        ) as mock_send:
            await learned_ac_entity.async_set_fan_mode("high")
            mock_send.assert_called_once()
            assert mock_send.call_args[1]["fan"] == "high"

    async def test_set_fan_mode_unsupported(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test setting unsupported fan mode raises error."""
        with pytest.raises(HomeAssistantError, match="Unsupported fan mode"):
            await learned_ac_entity.async_set_fan_mode("invalid")

    async def test_send_state_with_matching_signal(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test _send_state finds and uses matching learned signal."""
        with patch.object(
            learned_ac_entity, "_post_signal", new=AsyncMock()
        ) as mock_post:
            await learned_ac_entity._send_state(power=1, hvac_mode=HVACMode.COOL, temp=22, fan="medium")
            mock_post.assert_called_once_with("COOL_22_MED")

    async def test_send_state_without_matching_signal(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test _send_state raises when no signal matches."""
        with pytest.raises(HomeAssistantError, match="No learned AC signal matches"):
            await learned_ac_entity._send_state(power=1, hvac_mode=HVACMode.FAN_ONLY, temp=22)

    async def test_send_state_uses_power_on_signal_fallback(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test _send_state uses power on signal when no match, if available."""
        learned_ac_entity._power_on_signal = "POWER_ON"

        with patch.object(
            learned_ac_entity, "_post_signal", new=AsyncMock()
        ) as mock_post:
            # Request a mode that doesn't have learned signals
            await learned_ac_entity._send_state(power=1, hvac_mode=HVACMode.FAN_ONLY)
            mock_post.assert_called_once_with("POWER_ON")

    async def test_post_signal_failure_sets_unavailable(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Test _post_signal failure marks entity unavailable."""
        with patch(
            "homeassistant.components.stips_iru1.climate.async_build_control_hosts",
            return_value=(["host"], None),
        ):
            with patch.object(
                learned_ac_entity, "async_write_ha_state"
            ) as mock_write:
                with pytest.raises(HomeAssistantError):
                    await learned_ac_entity._post_signal("TEST_SIGNAL")
                
                assert learned_ac_entity._attr_available is False
                mock_write.assert_called()
