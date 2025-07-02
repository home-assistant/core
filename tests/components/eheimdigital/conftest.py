"""Configurations for the EHEIM Digital tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from eheimdigital.classic_led_ctrl import EheimDigitalClassicLEDControl
from eheimdigital.classic_vario import EheimDigitalClassicVario
from eheimdigital.heater import EheimDigitalHeater
from eheimdigital.hub import EheimDigitalHub
from eheimdigital.types import (
    AcclimatePacket,
    CCVPacket,
    ClassicVarioDataPacket,
    ClockPacket,
    CloudPacket,
    MoonPacket,
    UsrDtaPacket,
)
import pytest

from homeassistant.components.eheimdigital.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "eheimdigital"}, unique_id="00:00:00:00:00:01"
    )


@pytest.fixture
def classic_led_ctrl_mock():
    """Mock a classicLEDcontrol device."""
    classic_led_ctrl = EheimDigitalClassicLEDControl(
        MagicMock(spec=EheimDigitalHub),
        UsrDtaPacket(load_json_object_fixture("classic_led_ctrl/usrdta.json", DOMAIN)),
    )
    classic_led_ctrl.ccv = CCVPacket(
        load_json_object_fixture("classic_led_ctrl/ccv.json", DOMAIN)
    )
    classic_led_ctrl.moon = MoonPacket(
        load_json_object_fixture("classic_led_ctrl/moon.json", DOMAIN)
    )
    classic_led_ctrl.acclimate = AcclimatePacket(
        load_json_object_fixture("classic_led_ctrl/acclimate.json", DOMAIN)
    )
    classic_led_ctrl.cloud = CloudPacket(
        load_json_object_fixture("classic_led_ctrl/cloud.json", DOMAIN)
    )
    classic_led_ctrl.clock = ClockPacket(
        load_json_object_fixture("classic_led_ctrl/clock.json", DOMAIN)
    )
    return classic_led_ctrl


@pytest.fixture
def heater_mock():
    """Mock a Heater device."""
    heater = EheimDigitalHeater(
        MagicMock(spec=EheimDigitalHub),
        load_json_object_fixture("heater/usrdta.json", DOMAIN),
    )
    heater.heater_data = load_json_object_fixture("heater/heater_data.json", DOMAIN)
    return heater


@pytest.fixture
def classic_vario_mock():
    """Mock a classicVARIO device."""
    classic_vario = EheimDigitalClassicVario(
        MagicMock(spec=EheimDigitalHub),
        UsrDtaPacket(load_json_object_fixture("classic_vario/usrdta.json", DOMAIN)),
    )
    classic_vario.classic_vario_data = ClassicVarioDataPacket(
        load_json_object_fixture("classic_vario/classic_vario_data.json", DOMAIN)
    )
    return classic_vario


@pytest.fixture
def eheimdigital_hub_mock(
    classic_led_ctrl_mock: MagicMock,
    heater_mock: MagicMock,
    classic_vario_mock: MagicMock,
) -> Generator[AsyncMock]:
    """Mock eheimdigital hub."""
    with (
        patch(
            "homeassistant.components.eheimdigital.coordinator.EheimDigitalHub",
            spec=EheimDigitalHub,
        ) as eheimdigital_hub_mock,
        patch(
            "homeassistant.components.eheimdigital.config_flow.EheimDigitalHub",
            new=eheimdigital_hub_mock,
        ),
    ):
        eheimdigital_hub_mock.return_value.devices = {
            "00:00:00:00:00:01": classic_led_ctrl_mock,
            "00:00:00:00:00:02": heater_mock,
            "00:00:00:00:00:03": classic_vario_mock,
        }
        eheimdigital_hub_mock.return_value.main = classic_led_ctrl_mock
        yield eheimdigital_hub_mock


async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Initialize the integration."""

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.eheimdigital.coordinator.asyncio.Event", new=AsyncMock
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
