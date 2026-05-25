"""Tests for the Overkiz switch platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName, OverkizState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call, async_deliver_events, build_event

from tests.common import snapshot_platform

ON_OFF = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/16168460",
    "switch.music_room_pool_pump_on_off",
)
SWIMMING_POOL = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/16580352",
    "switch.pool_house",
)
RTD_OUTDOOR_SIREN = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "rtds://1234-1234-6233/4065441",
    "switch.willow_house_external_siren",
)
MYFOX_CAMERA = FixtureDevice(
    "setup/cloud_somfy_myfox_europe.json",
    "myfox://SOMFY_PROTECT-1234567890ABCDEF/jQ5ul40RVLnipT6JB8b3JK96tUsf14mR",
    "switch.outdoor_camera_camera_shutter",
)
# Bug: entity ID contains "undefinedtype_singleton" because the DomesticHotWaterTank
# description has no name set, and the #7 suffix makes it a sub-device.
DOMESTIC_HOT_WATER_TANK = FixtureDevice(
    "setup/cloud_somfy_myfox_europe.json",
    "io://1234-5678-1202/6019143#7",
    "switch.hot_water_tank_undefinedtype_singleton",
)


SNAPSHOT_FIXTURES = [
    ON_OFF,
    MYFOX_CAMERA,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to switch only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("device", "service", "expected_command", "expected_parameters"),
    [
        pytest.param(ON_OFF, SERVICE_TURN_ON, "on", None, id="on_off_turn_on"),
        pytest.param(ON_OFF, SERVICE_TURN_OFF, "off", None, id="on_off_turn_off"),
        pytest.param(
            SWIMMING_POOL, SERVICE_TURN_ON, "on", None, id="swimming_pool_turn_on"
        ),
        pytest.param(
            SWIMMING_POOL, SERVICE_TURN_OFF, "off", None, id="swimming_pool_turn_off"
        ),
        pytest.param(
            RTD_OUTDOOR_SIREN,
            SERVICE_TURN_ON,
            "on",
            None,
            id="rtd_outdoor_siren_turn_on",
        ),
        pytest.param(
            RTD_OUTDOOR_SIREN,
            SERVICE_TURN_OFF,
            "off",
            None,
            id="rtd_outdoor_siren_turn_off",
        ),
        pytest.param(
            MYFOX_CAMERA, SERVICE_TURN_ON, "open", None, id="myfox_camera_turn_on"
        ),
        pytest.param(
            MYFOX_CAMERA, SERVICE_TURN_OFF, "close", None, id="myfox_camera_turn_off"
        ),
        pytest.param(
            DOMESTIC_HOT_WATER_TANK,
            SERVICE_TURN_ON,
            "setForceHeating",
            ["on"],
            id="domestic_hot_water_tank_turn_on",
        ),
        pytest.param(
            DOMESTIC_HOT_WATER_TANK,
            SERVICE_TURN_OFF,
            "setForceHeating",
            ["off"],
            id="domestic_hot_water_tank_turn_off",
        ),
    ],
)
async def test_switch_service_call(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    device: FixtureDevice,
    service: str,
    expected_command: str,
    expected_parameters: list[str] | None,
) -> None:
    """Test switch service calls send the correct commands."""
    await setup_overkiz_integration(fixture=device.fixture)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: device.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=device.device_url,
        command_name=expected_command,
        **({"parameters": expected_parameters} if expected_parameters else {}),
    )


async def test_switch_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch reflects state changes from the device."""
    await setup_overkiz_integration(fixture=ON_OFF.fixture)

    assert hass.states.get(ON_OFF.entity_id).state == STATE_OFF

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=ON_OFF.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_ON_OFF.value,
                        "type": 3,
                        "value": "on",
                    },
                ],
            )
        ],
    )

    assert hass.states.get(ON_OFF.entity_id).state == STATE_ON


async def test_switch_unavailability(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch becomes unavailable when device goes offline."""
    await setup_overkiz_integration(fixture=ON_OFF.fixture)

    state = hass.states.get(ON_OFF.entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_UNAVAILABLE.value,
                device_url=ON_OFF.device_url,
            )
        ],
    )

    assert hass.states.get(ON_OFF.entity_id).state == STATE_UNAVAILABLE
