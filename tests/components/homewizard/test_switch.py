"""Test the switch entity for HomeWizard."""

from unittest.mock import MagicMock

from homewizard_energy import UnsupportedError
from homewizard_energy.errors import DisabledError, RequestError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import switch
from homeassistant.components.homewizard.const import UPDATE_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

pytestmark = [
    pytest.mark.usefixtures("init_integration"),
]


@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "HWE-P1",
            [
                "switch.device",
                "switch.device_switch_lock",
            ],
        ),
        (
            "HWE-WTR",
            [
                "switch.device",
                "switch.device_switch_lock",
            ],
        ),
        (
            "SDM230",
            [
                "switch.device",
                "switch.device_switch_lock",
            ],
        ),
        (
            "SDM630",
            [
                "switch.device",
                "switch.device_switch_lock",
            ],
        ),
        (
            "HWE-KWH1",
            [
                "switch.device",
                "switch.device_switch_lock",
            ],
        ),
        (
            "HWE-KWH3",
            [
                "switch.device",
                "switch.device_switch_lock",
            ],
        ),
    ],
)
async def test_entities_not_created_for_device(
    hass: HomeAssistant,
    entity_ids: list[str],
) -> None:
    """Ensures entities for a specific device are not created."""
    for entity_id in entity_ids:
        assert not hass.states.get(entity_id)


@pytest.mark.parametrize(
    ("device_fixture", "entity_id", "method", "parameter"),
    [
        ("HWE-SKT-11", "switch.device", "state_set", "power_on"),
        ("HWE-SKT-11", "switch.device_switch_lock", "state_set", "switch_lock"),
        ("HWE-SKT-11", "switch.device_cloud_connection", "system_set", "cloud_enabled"),
        ("HWE-SKT-21", "switch.device", "state_set", "power_on"),
        ("HWE-SKT-21", "switch.device_switch_lock", "state_set", "switch_lock"),
        ("HWE-SKT-21", "switch.device_cloud_connection", "system_set", "cloud_enabled"),
        ("HWE-WTR", "switch.device_cloud_connection", "system_set", "cloud_enabled"),
        ("SDM230", "switch.device_cloud_connection", "system_set", "cloud_enabled"),
        ("SDM630", "switch.device_cloud_connection", "system_set", "cloud_enabled"),
        ("HWE-KWH1", "switch.device_cloud_connection", "system_set", "cloud_enabled"),
        ("HWE-KWH3", "switch.device_cloud_connection", "system_set", "cloud_enabled"),
    ],
)
async def test_switch_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_homewizardenergy: MagicMock,
    snapshot: SnapshotAssertion,
    entity_id: str,
    method: str,
    parameter: str,
) -> None:
    """Test that switch handles state changes correctly."""
    assert (state := hass.states.get(entity_id))
    assert snapshot == state

    assert (entity_entry := entity_registry.async_get(entity_id))
    assert snapshot == entity_entry

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert snapshot == device_entry

    mocked_method = getattr(mock_homewizardenergy, method)

    # Turn power_on on
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mocked_method.mock_calls) == 1
    mocked_method.assert_called_with(**{parameter: True})

    # Turn power_on off
    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mocked_method.mock_calls) == 2
    mocked_method.assert_called_with(**{parameter: False})

    # Test request error handling
    mocked_method.side_effect = RequestError

    with pytest.raises(
        HomeAssistantError,
        match=r"^An error occurred while communicating with HomeWizard device$",
    ):
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    with pytest.raises(
        HomeAssistantError,
        match=r"^An error occurred while communicating with HomeWizard device$",
    ):
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # Test disabled error handling
    mocked_method.side_effect = DisabledError

    with pytest.raises(
        HomeAssistantError,
        match=r"^The local API is disabled$",
    ):
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    with pytest.raises(
        HomeAssistantError,
        match=r"^The local API is disabled$",
    ):
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


@pytest.mark.parametrize("device_fixture", ["HWE-SKT-11", "HWE-SKT-21"])
@pytest.mark.parametrize("exception", [RequestError, UnsupportedError])
@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("switch.device", "state"),
        ("switch.device_switch_lock", "state"),
        ("switch.device_cloud_connection", "system"),
    ],
)
async def test_switch_unreachable(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    exception: Exception,
    entity_id: str,
    method: str,
) -> None:
    """Test that unreachable devices are marked as unavailable."""
    mocked_method = getattr(mock_homewizardenergy, method)
    mocked_method.side_effect = exception
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE
