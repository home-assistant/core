"""Test the Hunter Douglas PowerView switch platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .const import MOCK_MAC

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize(
    ("api_version", "expected_quantity"),
    [
        pytest.param(1, 12, id="generation-1"),
        pytest.param(2, 12, id="generation-2"),
        pytest.param(3, 0, id="generation-3-unsupported"),
    ],
)
async def test_switch_quantity(
    hass: HomeAssistant,
    api_version: int,
    expected_quantity: int,
) -> None:
    """Test that schedule switches are created."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.async_entity_ids_count(SWITCH_DOMAIN) == expected_quantity


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2])
async def test_switch_state(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test all schedule switch states reflect their enabled fields."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    switches = [
        state
        for entity_id in hass.states.async_entity_ids(SWITCH_DOMAIN)
        if (state := hass.states.get(entity_id)) is not None
    ]

    assert sum(state.state == STATE_OFF for state in switches) == 11
    assert sum(state.state == STATE_ON for state in switches) == 1


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2])
async def test_switch_attributes(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test that schedule switches expose execution time and days attributes."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    switches = [
        state
        for entity_id in hass.states.async_entity_ids(SWITCH_DOMAIN)
        if (state := hass.states.get(entity_id)) is not None
    ]
    for switch in switches:
        assert "execution_time" in switch.attributes
        assert "execution_days" in switch.attributes


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2])
async def test_switch_enable(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test turning on a schedule switch enables the scheduled event."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "aiopvapi.resources.automation.Automation.set_state",
        new_callable=AsyncMock,
    ) as mock_set_state:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": f"switch.powerview_generation_{api_version}_38971_schedule"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_set_state.assert_called_once_with(True)


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2])
async def test_switch_disable(
    hass: HomeAssistant,
    api_version: int,
) -> None:
    """Test turning off a schedule switch disables the scheduled event."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"}, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    with patch(
        "aiopvapi.resources.automation.Automation.set_state",
        new_callable=AsyncMock,
    ) as mock_set_state:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {"entity_id": f"switch.powerview_generation_{api_version}_37484_schedule"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_set_state.assert_called_once_with(False)
