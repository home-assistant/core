"""Tests for the Overkiz switch platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import OverkizState
from pyoverkiz.models import Setup
import pytest
from pytest_homeassistant.common import snapshot_platform
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
from .helpers import (
    assert_command_call,
    async_deliver_events,
    device_state_changed_event,
    device_unavailable_event,
    oven_local_control_event,
    oven_remote_control_event,
)

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
# Sub-device (#7 suffix) whose device has no name set, so it takes the config
# entry title, and the entity id becomes device name + entity name.
DOMESTIC_HOT_WATER_TANK = FixtureDevice(
    "setup/cloud_somfy_myfox_europe.json",
    "io://1234-5678-1202/6019143#7",
    "switch.somfy_tahoma_switch_hot_water_tank",
)
OVEN = FixtureDevice(
    "setup/cloud_sauter_sop6615lb.json",
    "ogp://1234-5678-9123/16000211",
    "switch.oven",
)


SNAPSHOT_FIXTURES = [
    ON_OFF,
    MYFOX_CAMERA,
    OVEN,
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
        pytest.param(OVEN, SERVICE_TURN_ON, "start", None, id="oven_turn_on"),
        pytest.param(OVEN, SERVICE_TURN_OFF, "stop", None, id="oven_turn_off"),
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
            device_state_changed_event(
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
            device_unavailable_event(
                device_url=ON_OFF.device_url,
            )
        ],
    )

    assert hass.states.get(ON_OFF.entity_id).state == STATE_UNAVAILABLE


async def test_oven_switch_follows_cooking(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the oven switch reflects whether the oven is cooking."""
    await setup_overkiz_integration(fixture=OVEN.fixture)

    assert hass.states.get(OVEN.entity_id).state == STATE_OFF

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=OVEN.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_STARTED_STOPPED.value,
                        "type": 3,
                        "value": "started",
                    },
                ],
            )
        ],
    )

    assert hass.states.get(OVEN.entity_id).state == STATE_ON


def _block_local_control(setup: Setup) -> None:
    """Simulate an oven that has not been switched to its Wi-Fi mode."""
    state = setup.devices[0].states[OverkizState.OGP_UNAVAILABLE_FEATURES]
    state.value = [
        {"feature": "*", "commands": ["*"], "states": ["*"], "cause": "localControl"}
    ]


async def test_oven_switch_unavailable_during_local_control(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a blanket localControl block makes the oven switch unavailable."""
    await setup_overkiz_integration(fixture=OVEN.fixture, mutate=_block_local_control)

    assert hass.states.get(OVEN.entity_id).state == STATE_UNAVAILABLE


async def test_oven_switch_local_control_transition(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the oven switch follows localControl blocks delivered after setup."""
    await setup_overkiz_integration(fixture=OVEN.fixture)

    assert hass.states.get(OVEN.entity_id).state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass, freezer, mock_client, [oven_local_control_event(OVEN.device_url)]
    )

    assert hass.states.get(OVEN.entity_id).state == STATE_UNAVAILABLE

    await async_deliver_events(
        hass, freezer, mock_client, [oven_remote_control_event(OVEN.device_url)]
    )

    assert hass.states.get(OVEN.entity_id).state != STATE_UNAVAILABLE
