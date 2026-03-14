"""Tests for INELNET Blinds device actions."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.inelnet import InelnetRuntimeData
from homeassistant.components.inelnet.const import (
    ACTION_DOWN_SHORT,
    ACTION_PROGRAM,
    ACTION_UP_SHORT,
    DOMAIN,
)
from homeassistant.components.inelnet.device_action import (
    async_call_action_from_config,
    async_get_actions,
    async_validate_action_config,
)
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and add a config entry for inelnet."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="inelnet-test-entry",
        unique_id="192.168.1.67-1",
        data={"host": "192.168.1.67", "channels": [1]},
    )
    entry.runtime_data = InelnetRuntimeData(host="192.168.1.67", channels=[1])
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def device_id(hass: HomeAssistant, config_entry: MockConfigEntry) -> str:
    """Create a device and return its id."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, f"{config_entry.entry_id}-ch1")},
        name="INELNET Blinds channel 1",
    )
    return device.id


async def test_get_actions_returns_empty_for_unknown_device(
    hass: HomeAssistant,
) -> None:
    """Test async_get_actions returns empty list when device is not inelnet."""
    actions = await async_get_actions(hass, "unknown-device-id")
    assert actions == []


async def test_get_actions_returns_empty_when_identifier_domain_is_not_inelnet(
    hass: HomeAssistant,
) -> None:
    """Test device whose identifier has a different domain returns no actions."""
    other_entry = MockConfigEntry(domain="other_domain", entry_id="other-e1", data={})
    other_entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other_domain", "other-e1-ch1")},
        name="Other device",
    )
    actions = await async_get_actions(hass, device.id)
    assert actions == []


async def test_get_actions_returns_three_actions_for_inelnet_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_id: str,
) -> None:
    """Test async_get_actions returns short up, short down, program for inelnet device."""
    actions = await async_get_actions(hass, device_id)

    assert len(actions) == 3
    types = {a["type"] for a in actions}
    assert types == {ACTION_UP_SHORT, ACTION_DOWN_SHORT, ACTION_PROGRAM}
    assert all(a["domain"] == DOMAIN and a["device_id"] == device_id for a in actions)


async def test_validate_action_config_accepts_valid_config(
    hass: HomeAssistant,
    device_id: str,
) -> None:
    """Test async_validate_action_config returns config when valid."""
    config = {
        "domain": DOMAIN,
        "device_id": device_id,
        "type": ACTION_UP_SHORT,
    }
    validated = await async_validate_action_config(hass, config)
    assert validated == config


async def test_validate_action_config_raises_on_invalid_type(
    hass: HomeAssistant,
    device_id: str,
) -> None:
    """Test async_validate_action_config raises when type is invalid."""

    config = {
        "domain": DOMAIN,
        "device_id": device_id,
        "type": "invalid_action",
    }
    with pytest.raises(vol.Invalid):
        await async_validate_action_config(hass, config)


async def test_call_action_from_config_sends_command(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_id: str,
) -> None:
    """Test async_call_action_from_config calls send_command with correct args."""
    with patch(
        "homeassistant.components.inelnet.device_action.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        await async_call_action_from_config(
            hass,
            {
                CONF_DEVICE_ID: device_id,
                "domain": DOMAIN,
                "type": ACTION_PROGRAM,
            },
            {},
            None,
        )
    mock_send.assert_called_once_with(hass, "192.168.1.67", 1, 224)


async def test_call_action_from_config_no_op_when_device_unknown(
    hass: HomeAssistant,
) -> None:
    """Test async_call_action_from_config does nothing when device cannot be resolved."""
    with patch(
        "homeassistant.components.inelnet.device_action.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        await async_call_action_from_config(
            hass,
            {
                CONF_DEVICE_ID: "unknown-device",
                "domain": DOMAIN,
                "type": ACTION_UP_SHORT,
            },
            {},
            None,
        )
    mock_send.assert_not_called()


async def test_call_action_short_up_sends_correct_code(
    hass: HomeAssistant,
    device_id: str,
) -> None:
    """Test calling short up action sends ACT_UP_SHORT code."""
    with patch(
        "homeassistant.components.inelnet.device_action.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        await async_call_action_from_config(
            hass,
            {
                CONF_DEVICE_ID: device_id,
                "domain": DOMAIN,
                "type": ACTION_UP_SHORT,
            },
            {},
            None,
        )
    mock_send.assert_called_once()
    assert mock_send.call_args[0][3] == 176


async def test_call_action_short_down_sends_correct_code(
    hass: HomeAssistant,
    device_id: str,
) -> None:
    """Test calling short down action sends ACT_DOWN_SHORT code."""
    with patch(
        "homeassistant.components.inelnet.device_action.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        await async_call_action_from_config(
            hass,
            {
                CONF_DEVICE_ID: device_id,
                "domain": DOMAIN,
                "type": ACTION_DOWN_SHORT,
            },
            {},
            None,
        )
    mock_send.assert_called_once()
    assert mock_send.call_args[0][3] == 208


async def test_get_actions_returns_empty_when_identifier_has_no_ch_suffix(
    hass: HomeAssistant,
) -> None:
    """Test device with DOMAIN identifier but no '-ch' returns no actions."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="entry-no-ch",
        data={"host": "192.168.1.1", "channels": [1]},
    )
    entry.runtime_data = InelnetRuntimeData(host="192.168.1.1", channels=[1])
    entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "entry-no-ch-something")},
        name="Other",
    )
    actions = await async_get_actions(hass, device.id)
    assert actions == []


async def test_get_actions_returns_empty_when_channel_parse_fails(
    hass: HomeAssistant,
) -> None:
    """Test device with invalid channel in identifier returns no actions."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="entry-bad-ch",
        data={"host": "192.168.1.1", "channels": [1]},
    )
    entry.runtime_data = InelnetRuntimeData(host="192.168.1.1", channels=[1])
    entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "entry-bad-ch-nan")},
        name="Other",
    )
    actions = await async_get_actions(hass, device.id)
    assert actions == []


async def test_get_actions_returns_empty_when_device_linked_to_other_domain(
    hass: HomeAssistant,
) -> None:
    """Test device linked to non-inelnet config entry returns no actions."""
    other_entry = MockConfigEntry(
        domain="other_domain",
        entry_id="other-entry",
        data={},
    )
    other_entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, "other-entry-ch1")},
        name="Other",
    )
    actions = await async_get_actions(hass, device.id)
    assert actions == []


async def test_get_actions_returns_empty_when_entry_has_no_runtime_data(
    hass: HomeAssistant,
) -> None:
    """Test device linked to inelnet entry without runtime_data returns no actions."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="inelnet-no-runtime",
        data={"host": "192.168.1.1", "channels": [1]},
    )
    entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "inelnet-no-runtime-ch1")},
        name="INELNET channel 1",
    )
    actions = await async_get_actions(hass, device.id)
    assert actions == []


async def test_get_actions_returns_empty_when_runtime_data_has_no_host(
    hass: HomeAssistant,
) -> None:
    """Test entry with runtime_data host empty returns no actions."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="inelnet-no-host",
        data={"host": "192.168.1.1", "channels": [1]},
    )
    entry.runtime_data = InelnetRuntimeData(host="", channels=[1])
    entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "inelnet-no-host-ch1")},
        name="INELNET channel 1",
    )
    actions = await async_get_actions(hass, device.id)
    assert actions == []


async def test_call_action_from_config_no_op_when_type_invalid(
    hass: HomeAssistant,
    device_id: str,
) -> None:
    """Test async_call_action_from_config does not call send_command when type is unknown."""
    with patch(
        "homeassistant.components.inelnet.device_action.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        await async_call_action_from_config(
            hass,
            {
                CONF_DEVICE_ID: device_id,
                "domain": DOMAIN,
                "type": "unknown_action_type",
            },
            {},
            None,
        )
    mock_send.assert_not_called()
