"""Test helpers for VoIP integration."""

import asyncio
from collections.abc import Generator
import contextlib
from unittest.mock import AsyncMock, Mock, create_autospec, patch

import pytest
from voip_utils import CallInfo
from voip_utils.sip import get_sip_endpoint

from homeassistant.components import assist_satellite, voip
from homeassistant.components.assist_satellite import AssistSatelliteEntity
from homeassistant.components.voip import DOMAIN
from homeassistant.components.voip.assist_satellite import VoipAssistSatellite
from homeassistant.components.voip.devices import VoIPDevice, VoIPDevices
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.tts.conftest import (
    mock_tts_cache_dir_fixture_autouse,  # noqa: F401
)


@pytest.fixture(autouse=True)
async def load_homeassistant(hass: HomeAssistant) -> None:
    """Load the homeassistant integration."""
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.fixture(autouse=True)
def reduce_satellite_delays() -> Generator[None]:
    """Shorten the delays that the satellite always waits out.

    Tests must send audio chunks more often than _HANGUP_SEC, or the satellite
    treats the gap as the caller hanging up. Timeouts that only elapse when audio
    never arrives are left alone: they cost nothing unless a test exercises them.
    """
    with (
        patch("homeassistant.components.voip.assist_satellite._HANGUP_SEC", 0.2),
        patch(
            "homeassistant.components.voip.assist_satellite._ANNOUNCEMENT_BEFORE_DELAY",
            0.1,
        ),
        patch(
            "homeassistant.components.voip.assist_satellite._ANNOUNCEMENT_AFTER_DELAY",
            0.1,
        ),
    ):
        yield


@pytest.fixture
def silent_tones() -> Generator[None]:
    """Give every tone empty audio.

    A real tone is up to two seconds streamed in real time, which outlasts the
    shortened hangup window. The tone paths still run, so the processing tone
    still gates _send_tts.
    """
    with patch.object(VoipAssistSatellite, "_load_pcm", return_value=b""):
        yield


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_voip(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up VoIP integration."""
    with patch(
        "homeassistant.components.voip._create_sip_server",
        return_value=(Mock(), AsyncMock()),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
        yield


@pytest.fixture
async def voip_devices(
    hass: HomeAssistant, config_entry: MockConfigEntry, setup_voip: None
) -> VoIPDevices:
    """Get VoIP devices object from a configured instance."""
    return config_entry.runtime_data.domain_data.devices


@pytest.fixture
def call_info() -> CallInfo:
    """Fake call info."""
    return CallInfo(
        caller_endpoint=get_sip_endpoint("192.168.1.210", 5060),
        local_endpoint=get_sip_endpoint("192.168.1.10", 5060),
        caller_rtp_port=5004,
        server_ip="192.168.1.10",
        headers={
            "via": "SIP/2.0/UDP 192.168.1.210:5060;branch=z9hG4bK912387041;rport",
            "from": "<sip:IPCall@192.168.1.210:5060>;tag=1836983217",
            "to": "<sip:192.168.1.10:5060>",
            "call-id": "860888843-5060-9@BJC.BGI.B.CBA",
            "cseq": "80 INVITE",
            "contact": "<sip:IPCall@192.168.1.210:5060>",
            "max-forwards": "70",
            "user-agent": "Grandstream HT801 1.0.17.5",
            "supported": "replaces, path, timer, eventlist",
            "allow": "INVITE, ACK, OPTIONS, CANCEL, BYE,"
            " SUBSCRIBE, NOTIFY, INFO, REFER, UPDATE",
            "content-type": "application/sdp",
            "accept": "application/sdp, application/dtmf-relay",
            "content-length": "480",
        },
    )


@pytest.fixture
async def voip_device(
    hass: HomeAssistant, voip_devices: VoIPDevices, call_info: CallInfo
) -> VoIPDevice:
    """Get a VoIP device fixture."""
    device = voip_devices.async_get_or_create(call_info)
    # to make sure all platforms are set up
    await hass.async_block_till_done()
    return device


@pytest.fixture
async def satellite(
    hass: HomeAssistant,
    voip_device: VoIPDevice,
):
    """Create VoipAssistSatellite for use in tests."""
    satellite = async_get_satellite_entity(hass, voip.DOMAIN, voip_device.voip_id)
    assert isinstance(satellite, VoipAssistSatellite)

    mock_send_audio = create_autospec(satellite.send_audio)
    satellite.send_audio = mock_send_audio

    yield satellite

    task = satellite._sender_task
    if task is not None:
        task.cancel()
    satellite.disconnect()
    if task is not None:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await hass.async_block_till_done(wait_background_tasks=True)


def async_get_satellite_entity(
    hass: HomeAssistant, domain: str, unique_id_prefix: str
) -> AssistSatelliteEntity | None:
    """Get Assist satellite entity."""
    ent_reg = er.async_get(hass)
    satellite_entity_id = ent_reg.async_get_entity_id(
        Platform.ASSIST_SATELLITE, domain, f"{unique_id_prefix}-assist_satellite"
    )
    if satellite_entity_id is None:
        return None
    assert not satellite_entity_id.endswith("none")

    component: EntityComponent[AssistSatelliteEntity] = hass.data[
        assist_satellite.DOMAIN
    ]
    return component.get_entity(satellite_entity_id)
