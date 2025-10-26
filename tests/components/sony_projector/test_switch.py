"""Tests for the Sony Projector compatibility switch platform."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from homeassistant.components import sony_projector
from homeassistant.components.sony_projector.const import (
    CONF_TITLE,
    DATA_YAML_SWITCH_HOSTS,
    DOMAIN,
)
from homeassistant.components.sony_projector.switch import (
    SonyProjectorCompatSwitch,
    async_setup_entry,
    async_setup_platform,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_async_setup_platform_tracks_yaml_hosts_and_imports(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test YAML switch setup tracks hosts and triggers an import flow."""

    hass.config_entries.flow.async_init = AsyncMock(return_value=None)
    caplog.set_level("WARNING")

    with patch(
        "homeassistant.components.sony_projector.switch.ir.async_create_issue",
        MagicMock(),
    ) as mock_issue:
        await async_setup_platform(
            hass,
            {CONF_HOST: "1.1.1.1", CONF_NAME: "Compat"},
            lambda entities: None,
        )
        await hass.async_block_till_done()

    assert "deprecated" in caplog.text
    yaml_hosts = hass.data[DOMAIN][DATA_YAML_SWITCH_HOSTS]
    assert yaml_hosts == {"1.1.1.1"}
    hass.config_entries.flow.async_init.assert_awaited_once()
    assert mock_issue.call_count == 1


async def test_async_setup_entry_adds_compat_switch_when_yaml_present(
    hass: HomeAssistant,
) -> None:
    """Test the compatibility switch is created when YAML for the host remains."""

    hass.data.setdefault(DOMAIN, {})[DATA_YAML_SWITCH_HOSTS] = {"1.2.3.4"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_TITLE: "Legacy"},
    )
    entry.add_to_hass(hass)
    client = AsyncMock()
    entry.runtime_data = sony_projector.SonyProjectorRuntimeData(client=client)

    added_entities: list[SonyProjectorCompatSwitch] = []

    def _async_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, entry, _async_add_entities)

    assert len(added_entities) == 1
    entity = added_entities[0]
    assert isinstance(entity, SonyProjectorCompatSwitch)
    assert entity.unique_id == "1.2.3.4-switch"


async def test_async_setup_entry_removes_entity_when_yaml_missing(
    hass: HomeAssistant,
) -> None:
    """Test stale compatibility switches are removed when YAML is gone."""

    hass.data.setdefault(DOMAIN, {})[DATA_YAML_SWITCH_HOSTS] = set()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_TITLE: "Legacy"},
    )
    entry.add_to_hass(hass)
    client = AsyncMock()
    entry.runtime_data = sony_projector.SonyProjectorRuntimeData(client=client)

    registry = er.async_get(hass)
    entity_entry = registry.async_get_or_create(
        "switch",
        DOMAIN,
        "1.2.3.4-switch",
        suggested_object_id="legacy_projector",
    )

    hass.is_running = True

    with (
        patch(
            "homeassistant.components.sony_projector.switch.ir.async_create_issue",
            MagicMock(),
        ) as mock_issue,
        patch(
            "homeassistant.components.sony_projector.switch.ir.async_delete_issue",
            MagicMock(),
        ) as mock_delete,
        patch(
            "homeassistant.components.sony_projector.switch._has_legacy_references",
            return_value=True,
        ) as mock_has_refs,
    ):
        await async_setup_entry(hass, entry, lambda entities: None)

    assert registry.async_get(entity_entry.entity_id) is None
    assert mock_has_refs.called
    assert mock_issue.call_count == 1
    assert mock_delete.call_count == 0


async def test_compat_switch_updates_and_controls_projector(
    hass: HomeAssistant,
) -> None:
    """Test the compatibility switch proxies projector state and control."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_TITLE: "Legacy"},
    )
    client = AsyncMock()
    client.async_get_state.return_value = sony_projector.client.ProjectorState(
        is_on=True
    )

    entity = SonyProjectorCompatSwitch(entry, client)

    await entity.async_update()
    assert entity.available is True
    assert entity.is_on is True

    await entity.async_turn_off()
    client.async_set_power.assert_awaited_once_with(False)
    assert entity.available is True
    assert entity.is_on is False

    client.async_set_power.reset_mock()
    client.async_set_power.side_effect = sony_projector.client.ProjectorClientError
    await entity.async_turn_on()
    assert entity.available is False
    assert client.async_set_power.await_args_list[0] == call(True)


async def test_compat_switch_async_added_to_hass_creates_issue(
    hass: HomeAssistant,
) -> None:
    """Test the compatibility switch surfaces a migration hint when referenced."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_TITLE: "Legacy"},
    )
    client = AsyncMock()
    entity = SonyProjectorCompatSwitch(entry, client)
    entity.hass = hass
    entity.entity_id = "switch.sony_projector_legacy"

    hass.is_running = True

    with (
        patch(
            "homeassistant.components.sony_projector.switch._has_legacy_references",
            return_value=True,
        ) as mock_has_refs,
        patch(
            "homeassistant.components.sony_projector.switch.ir.async_create_issue",
            MagicMock(),
        ) as mock_issue,
        patch(
            "homeassistant.components.sony_projector.switch.ir.async_delete_issue",
            MagicMock(),
        ) as mock_delete,
    ):
        await entity.async_added_to_hass()

    mock_has_refs.assert_called_once_with(hass, "switch.sony_projector_legacy")
    assert mock_issue.call_count == 1
    assert mock_delete.call_count == 0
