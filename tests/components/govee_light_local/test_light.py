"""Test Govee light local."""

from unittest.mock import AsyncMock, MagicMock, patch

from govee_local_api import GoveeDevice

from homeassistant.components.govee_light_local.const import DOMAIN
from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES, ColorMode
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import DEFAULT_CAPABILITEIS

from tests.common import MockConfigEntry


async def test_light_known_device(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test adding a known device."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITEIS,
        )
    ]

    with patch(
        "homeassistant.components.govee_light_local.coordinator.GoveeController",
        return_value=mock_govee_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.H615A")
        assert light is not None

        color_modes = light.attributes[ATTR_SUPPORTED_COLOR_MODES]
        assert set(color_modes) == {ColorMode.COLOR_TEMP, ColorMode.RGB}

        # Remove
        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("light.H615A") is None


async def test_light_unknown_device(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test adding an unknown device."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.101",
            fingerprint="unkown_device",
            sku="XYZK",
            capabilities=None,
        )
    ]

    with patch(
        "homeassistant.components.govee_light_local.coordinator.GoveeController",
        return_value=mock_govee_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.XYZK")
        assert light is not None

        assert light.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]


async def test_light_remove(hass: HomeAssistant, mock_govee_api: AsyncMock) -> None:
    """Test adding a known device."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd1",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITEIS,
        )
    ]

    with patch(
        "homeassistant.components.govee_light_local.coordinator.GoveeController",
        return_value=mock_govee_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("light.H615A") is not None

        # Remove 1
        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0


async def test_light_setup_retry(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test adding an unknown device."""

    mock_govee_api.devices = []

    with patch(
        "homeassistant.components.govee_light_local.coordinator.GoveeController",
        return_value=mock_govee_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.govee_light_local.DISCOVERY_TIMEOUT",
            0,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_light_on_off(hass: HomeAssistant, mock_govee_api: MagicMock) -> None:
    """Test adding a known device."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITEIS,
        )
    ]

    with patch(
        "homeassistant.components.govee_light_local.coordinator.GoveeController",
        return_value=mock_govee_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.H615A")
        assert light is not None
        assert light.state == "off"

        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": light.entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.H615A")
        assert light is not None
        assert light.state == "on"
        mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], True)

        # Turn off
        await hass.services.async_call(
            "light",
            "turn_off",
            {"entity_id": light.entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.H615A")
        assert light is not None
        assert light.state == "off"
        mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], False)


async def test_light_brightness(hass: HomeAssistant, mock_govee_api: MagicMock) -> None:
    """Test changing brightness."""
    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITEIS,
        )
    ]

    with patch(
        "homeassistant.components.govee_light_local.coordinator.GoveeController",
        return_value=mock_govee_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.H615A")
        assert light is not None
        assert light.state == "off"

        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": light.entity_id, "brightness_pct": 50},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.H615A")
        assert light is not None
        assert light.state == "on"
        mock_govee_api.set_brightness.assert_awaited_with(mock_govee_api.devices[0], 50)
        assert light.attributes["brightness"] == 127

        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": light.entity_id, "brightness": 255},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.H615A")
        assert light is not None
        assert light.state == "on"
        assert light.attributes["brightness"] == 255
        mock_govee_api.set_brightness.assert_awaited_with(
            mock_govee_api.devices[0], 100
        )

        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": light.entity_id, "brightness": 255},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.H615A")
        assert light is not None
        assert light.state == "on"
        assert light.attributes["brightness"] == 255
        mock_govee_api.set_brightness.assert_awaited_with(
            mock_govee_api.devices[0], 100
        )


async def test_light_color(hass: HomeAssistant, mock_govee_api: MagicMock) -> None:
    """Test changing brightness."""
    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITEIS,
        )
    ]

    with patch(
        "homeassistant.components.govee_light_local.coordinator.GoveeController",
        return_value=mock_govee_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.H615A")
        assert light is not None
        assert light.state == "off"

        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": light.entity_id, "rgb_color": [100, 255, 50]},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.H615A")
        assert light is not None
        assert light.state == "on"
        assert light.attributes["rgb_color"] == (100, 255, 50)
        assert light.attributes["color_mode"] == ColorMode.RGB

        mock_govee_api.set_color.assert_awaited_with(
            mock_govee_api.devices[0], rgb=(100, 255, 50), temperature=None
        )

        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": light.entity_id, "kelvin": 4400},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.H615A")
        assert light is not None
        assert light.state == "on"
        assert light.attributes["color_temp_kelvin"] == 4400
        assert light.attributes["color_mode"] == ColorMode.COLOR_TEMP

        mock_govee_api.set_color.assert_awaited_with(
            mock_govee_api.devices[0], rgb=None, temperature=4400
        )
