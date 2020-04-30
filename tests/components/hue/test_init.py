"""Test Hue setup process."""
from unittest.mock import Mock

from homeassistant.components import hue
from homeassistant.setup import async_setup_component

from tests.async_mock import AsyncMock, patch
from tests.common import MockConfigEntry, mock_coro


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a bridge."""
    assert await async_setup_component(hass, hue.DOMAIN, {}) is True

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0

    # No configs stored
    assert hass.data[hue.DOMAIN] == {}


async def test_setup_defined_hosts_known_auth(hass):
    """Test we don't initiate a config entry if config bridge is known."""
    MockConfigEntry(domain="hue", data={"host": "0.0.0.0"}).add_to_hass(hass)

    with patch.object(hue, "async_setup_entry", return_value=mock_coro(True)):
        assert (
            await async_setup_component(
                hass,
                hue.DOMAIN,
                {
                    hue.DOMAIN: {
                        hue.CONF_BRIDGES: [
                            {
                                hue.CONF_HOST: "0.0.0.0",
                                hue.CONF_ALLOW_HUE_GROUPS: False,
                                hue.CONF_ALLOW_UNREACHABLE: True,
                            },
                            {hue.CONF_HOST: "1.1.1.1"},
                        ]
                    }
                },
            )
            is True
        )

    # Flow started for discovered bridge
    assert len(hass.config_entries.flow.async_progress()) == 1

    # Config stored for domain.
    assert hass.data[hue.DATA_CONFIGS] == {
        "0.0.0.0": {
            hue.CONF_HOST: "0.0.0.0",
            hue.CONF_ALLOW_HUE_GROUPS: False,
            hue.CONF_ALLOW_UNREACHABLE: True,
        },
        "1.1.1.1": {
            hue.CONF_HOST: "1.1.1.1",
            hue.CONF_ALLOW_HUE_GROUPS: True,
            hue.CONF_ALLOW_UNREACHABLE: False,
        },
    }


async def test_setup_defined_hosts_no_known_auth(hass):
    """Test we initiate config entry if config bridge is not known."""
    assert (
        await async_setup_component(
            hass,
            hue.DOMAIN,
            {
                hue.DOMAIN: {
                    hue.CONF_BRIDGES: {
                        hue.CONF_HOST: "0.0.0.0",
                        hue.CONF_ALLOW_HUE_GROUPS: False,
                        hue.CONF_ALLOW_UNREACHABLE: True,
                    }
                }
            },
        )
        is True
    )

    # Flow started for discovered bridge
    assert len(hass.config_entries.flow.async_progress()) == 1

    # Config stored for domain.
    assert hass.data[hue.DATA_CONFIGS] == {
        "0.0.0.0": {
            hue.CONF_HOST: "0.0.0.0",
            hue.CONF_ALLOW_HUE_GROUPS: False,
            hue.CONF_ALLOW_UNREACHABLE: True,
        }
    }


async def test_config_passed_to_config_entry(hass):
    """Test that configured options for a host are loaded via config entry."""
    entry = MockConfigEntry(domain=hue.DOMAIN, data={"host": "0.0.0.0"})
    entry.add_to_hass(hass)
    mock_registry = Mock()
    with patch.object(hue, "HueBridge") as mock_bridge, patch(
        "homeassistant.helpers.device_registry.async_get_registry",
        return_value=mock_registry,
    ):
        mock_bridge.return_value.async_setup = AsyncMock(return_value=True)
        mock_bridge.return_value.api.config = Mock(
            mac="mock-mac",
            bridgeid="mock-bridgeid",
            modelid="mock-modelid",
            swversion="mock-swversion",
        )
        # Can't set name via kwargs
        mock_bridge.return_value.api.config.name = "mock-name"
        assert (
            await async_setup_component(
                hass,
                hue.DOMAIN,
                {
                    hue.DOMAIN: {
                        hue.CONF_BRIDGES: {
                            hue.CONF_HOST: "0.0.0.0",
                            hue.CONF_ALLOW_HUE_GROUPS: False,
                            hue.CONF_ALLOW_UNREACHABLE: True,
                        }
                    }
                },
            )
            is True
        )

    assert len(mock_bridge.mock_calls) == 2
    p_hass, p_entry, p_allow_unreachable, p_allow_groups = mock_bridge.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry is entry
    assert p_allow_unreachable is True
    assert p_allow_groups is False

    assert len(mock_registry.mock_calls) == 1
    assert mock_registry.mock_calls[0][2] == {
        "config_entry_id": entry.entry_id,
        "connections": {("mac", "mock-mac")},
        "identifiers": {("hue", "mock-bridgeid")},
        "manufacturer": "Signify",
        "name": "mock-name",
        "model": "mock-modelid",
        "sw_version": "mock-swversion",
    }


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(domain=hue.DOMAIN, data={"host": "0.0.0.0"})
    entry.add_to_hass(hass)

    with patch.object(hue, "HueBridge") as mock_bridge, patch(
        "homeassistant.helpers.device_registry.async_get_registry",
        return_value=mock_coro(Mock()),
    ):
        mock_bridge.return_value.async_setup = AsyncMock(return_value=True)
        mock_bridge.return_value.api.config = Mock(bridgeid="aabbccddeeff")
        assert await async_setup_component(hass, hue.DOMAIN, {}) is True

    assert len(mock_bridge.return_value.mock_calls) == 1

    mock_bridge.return_value.async_reset = AsyncMock(return_value=True)
    assert await hue.async_unload_entry(hass, entry)
    assert len(mock_bridge.return_value.async_reset.mock_calls) == 1
    assert hass.data[hue.DOMAIN] == {}


async def test_setting_unique_id(hass):
    """Test we set unique ID if not set yet."""
    entry = MockConfigEntry(domain=hue.DOMAIN, data={"host": "0.0.0.0"})
    entry.add_to_hass(hass)

    with patch.object(hue, "HueBridge") as mock_bridge, patch(
        "homeassistant.helpers.device_registry.async_get_registry",
        return_value=mock_coro(Mock()),
    ):
        mock_bridge.return_value.async_setup = AsyncMock(return_value=True)
        mock_bridge.return_value.api.config = Mock(bridgeid="mock-id")
        assert await async_setup_component(hass, hue.DOMAIN, {}) is True

    assert entry.unique_id == "mock-id"


async def test_security_vuln_check(hass):
    """Test that we report security vulnerabilities."""
    assert await async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(domain=hue.DOMAIN, data={"host": "0.0.0.0"})
    entry.add_to_hass(hass)

    config = Mock(bridgeid="", mac="", modelid="BSB002", swversion="1935144020")
    config.name = "Hue"

    with patch.object(
        hue,
        "HueBridge",
        Mock(
            return_value=Mock(
                async_setup=AsyncMock(return_value=True), api=Mock(config=config)
            )
        ),
    ):

        assert await async_setup_component(hass, "hue", {})

    await hass.async_block_till_done()

    state = hass.states.get("persistent_notification.hue_hub_firmware")
    assert state is not None
    assert "CVE-2020-6007" in state.attributes["message"]
