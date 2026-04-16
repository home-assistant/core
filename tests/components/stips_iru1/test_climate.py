"""Tests for stips_iru1 climate entities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.stips_iru1 import climate as stips_climate
from homeassistant.components.stips_iru1.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from tests.common import MockConfigEntry


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
        assert (DOMAIN, "stips-iru1-12345") in info["identifiers"]
        assert (CONNECTION_NETWORK_MAC, "AA:BB:CC:DD:EE:FF") in info["connections"]

    def test_properties(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Validate protocol AC property mapping."""
        protocol_ac_entity._state.update(
            {
                "power": 1,
                "mode": 2,
                "fan": 4,
                "temp": 24,
                "swingV": 1,
                "swingH": 0,
            }
        )

        assert protocol_ac_entity.hvac_mode is HVACMode.HEAT
        assert protocol_ac_entity.target_temperature == 24.0
        assert protocol_ac_entity.fan_mode == "high"
        assert protocol_ac_entity.swing_mode == "vertical"
        assert protocol_ac_entity.extra_state_attributes["protocol"] == 42

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
        with pytest.raises(HomeAssistantError, match="Unsupported HVAC mode"):
            await protocol_ac_entity.async_set_hvac_mode(HVACMode.HEAT_COOL)

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
                session.post = MagicMock(side_effect=TimeoutError())

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

    async def test_send_update_http_error(
        self, protocol_ac_entity: stips_climate.StipsIruClimate
    ) -> None:
        """Validate HTTP error handling for local AC requests."""
        response = AsyncMock()
        response.status = 500
        response.text = AsyncMock(return_value="failure")
        context = AsyncMock()
        context.__aenter__.return_value = response
        context.__aexit__.return_value = None

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
            session.post = MagicMock(return_value=context)
            get_session.return_value = session

            with pytest.raises(HomeAssistantError, match="Local AC request failed"):
                await protocol_ac_entity._send_update(power=1)


async def test_async_setup_entry_creates_expected_entities(
    hass: HomeAssistant,
) -> None:
    """Climate setup should create protocol and learned AC entities only."""
    entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "devices": [
                {
                    "uniqueName": "stips-iru1-12345",
                    "name": "Main Device",
                    "deviceIP": "192.168.1.10",
                    "deviceMac": "AA:BB:CC:DD:EE:FF",
                    "online": True,
                    "remotes": [
                        {
                            "id": 0,
                            "type": "AC",
                            "friendlyName": "Protocol AC",
                            "model": {"protocol": 7},
                        },
                        {
                            "id": "skip-ac",
                            "type": "AC",
                            "friendlyName": "Broken AC",
                            "model": {},
                        },
                        {
                            "id": "learned-ac",
                            "type": "LearnedAc",
                            "friendlyName": "Learned AC",
                            "model": {
                                "frequency": 38000,
                                "signals": [
                                    {
                                        "mode": "cool",
                                        "temperature": 22,
                                        "fanSpeed": "medium",
                                        "signal": "COOL",
                                    }
                                ],
                            },
                        },
                    ],
                }
            ]
        },
    )
    entities: list[stips_climate.ClimateEntity] = []

    await stips_climate.async_setup_entry(hass, entry, entities.extend)

    assert len(entities) == 2
    assert any(entity.unique_id.endswith("_climate_0") for entity in entities)
    assert any("learned_ac" in entity.unique_id for entity in entities)


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

    async def test_basic_controls(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Validate learned AC control methods map to _send_state or _post_signal."""
        with patch.object(learned_ac_entity, "_send_state", new=AsyncMock()) as send:
            await learned_ac_entity.async_turn_on()
            send.assert_called_with(power=1, hvac_mode=HVACMode.COOL)

            await learned_ac_entity.async_set_hvac_mode(HVACMode.HEAT)
            assert send.call_args.kwargs["hvac_mode"] == HVACMode.HEAT

            await learned_ac_entity.async_set_temperature(temperature=50)
            assert send.call_args.kwargs["temp"] == 22

            await learned_ac_entity.async_set_fan_mode("low")
            assert send.call_args.kwargs["fan"] == "low"

        with patch.object(learned_ac_entity, "_post_signal", new=AsyncMock()) as post:
            with patch.object(learned_ac_entity, "async_write_ha_state"):
                await learned_ac_entity.async_turn_off()
            post.assert_called_once_with("POWER_OFF")

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
        with (
            patch.object(learned_ac_entity, "_post_signal", new=AsyncMock()) as post,
            patch.object(learned_ac_entity, "async_write_ha_state"),
        ):
            await learned_ac_entity._send_state(
                power=1,
                hvac_mode=HVACMode.COOL,
                temp=22,
                fan="medium",
            )
            post.assert_called_once_with("COOL_22_MED")

        learned_ac_entity._power_on_signal = "POWER_ON"
        with (
            patch.object(learned_ac_entity, "_post_signal", new=AsyncMock()) as post,
            patch.object(learned_ac_entity, "async_write_ha_state"),
        ):
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
            session.post = MagicMock(side_effect=TimeoutError())

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

    async def test_post_signal_http_error(
        self, learned_ac_entity: stips_climate.StipsIruLearnedAcClimate
    ) -> None:
        """Validate HTTP error handling for learned AC signal posts."""
        response = AsyncMock()
        response.status = 500
        response.text = AsyncMock(return_value="failure")
        context = AsyncMock()
        context.__aenter__.return_value = response
        context.__aexit__.return_value = None

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
            session.post = MagicMock(return_value=context)
            get_session.return_value = session

            with pytest.raises(HomeAssistantError, match="Local IR request failed"):
                await learned_ac_entity._post_signal("SIG")
