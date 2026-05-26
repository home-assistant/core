"""Switch platform tests for iAquaLink."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.systems.iaqua.device import IaquaAuxSwitch
from iaqualink.systems.iaqua.system import IaquaSystem
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import (
    assert_platform_setup,
    get_aqualink_device,
    get_aqualink_system,
    setup_entry,
)

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all switch entities are created correctly."""
    await assert_platform_setup(
        hass, config_entry, client, entity_registry, snapshot, SWITCH_DOMAIN
    )


async def _setup_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    *,
    label: str,
    state: str,
) -> tuple[IaquaSystem, object, str, object]:
    """Set up the integration with a single switch entity."""
    system = get_aqualink_system(client, cls=IaquaSystem)
    system.online = True
    system.update = AsyncMock()
    switch = get_aqualink_device(
        system,
        name=label.lower().replace(" ", "_"),
        cls=IaquaAuxSwitch,
        data={"state": state, "aux": "1", "label": label},
    )
    system.get_devices = AsyncMock(return_value={switch.name: switch})
    system.set_aux = AsyncMock()

    await setup_entry(hass, config_entry, system)

    entity_ids = hass.states.async_entity_ids(SWITCH_DOMAIN)
    assert len(entity_ids) == 1
    entity_id = entity_ids[0]
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    return system, switch, entity_id, entity_state


@pytest.mark.parametrize(
    ("label", "expected_icon"),
    [
        pytest.param("Cleaner", "mdi:robot-vacuum", id="cleaner"),
        pytest.param("Waterfall", "mdi:fountain", id="waterfall"),
        pytest.param("Spa Dscnt", "mdi:fountain", id="descent"),
        pytest.param("Filter Pump", "mdi:fan", id="pump"),
        pytest.param("Spa Blower", "mdi:fan", id="blower"),
        pytest.param("Pool Heater", "mdi:radiator", id="heater"),
        pytest.param("Auxiliary", None, id="default"),
    ],
)
async def test_switch_icons(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    label: str,
    expected_icon: str | None,
) -> None:
    """Test switch icons are derived from the device label."""
    _, _, _, entity_state = await _setup_switch(
        hass,
        config_entry,
        client,
        label=label,
        state="1",
    )

    assert entity_state.attributes.get("icon") == expected_icon
    assert entity_state.state == STATE_ON


@pytest.mark.parametrize(
    ("service", "initial_state", "expected_state"),
    [
        pytest.param(SERVICE_TURN_ON, "0", STATE_ON, id="turn-on"),
        pytest.param(SERVICE_TURN_OFF, "1", STATE_OFF, id="turn-off"),
    ],
)
async def test_switch_actions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    service: str,
    initial_state: str,
    expected_state: str,
) -> None:
    """Test switch services update Home Assistant state."""
    system, switch, entity_id, _ = await _setup_switch(
        hass,
        config_entry,
        client,
        label="Auxiliary",
        state=initial_state,
    )

    async def set_aux(_: str) -> None:
        switch.data["state"] = "1" if service == SERVICE_TURN_ON else "0"

    system.set_aux = AsyncMock(side_effect=set_aux)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == expected_state


@pytest.mark.parametrize(
    ("raised_exception", "expected_exception", "match"),
    [
        pytest.param(
            AqualinkServiceException,
            HomeAssistantError,
            "Aqualink error: AqualinkServiceException",
            id="service",
        ),
        pytest.param(
            TimeoutError(),
            HomeAssistantError,
            "Aqualink error: TimeoutError",
            id="timeout",
        ),
        pytest.param(
            httpx.HTTPError("boom"),
            HomeAssistantError,
            "Aqualink error: boom",
            id="http",
        ),
        pytest.param(
            AqualinkServiceUnauthorizedException,
            ConfigEntryAuthFailed,
            "Invalid credentials for iAquaLink",
            id="unauthorized",
        ),
    ],
)
async def test_switch_turn_off_errors_leave_state_unchanged(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    raised_exception: Exception | type[Exception],
    expected_exception: type[Exception],
    match: str,
) -> None:
    """Test turn-off errors are surfaced through the switch service call."""
    system, _, entity_id, _ = await _setup_switch(
        hass,
        config_entry,
        client,
        label="Auxiliary",
        state="1",
    )
    system.set_aux = AsyncMock(side_effect=raised_exception)

    with pytest.raises(expected_exception, match=match):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == STATE_ON
