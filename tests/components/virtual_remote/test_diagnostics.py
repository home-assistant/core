"""Tests for Virtual Remote diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from homeassistant.components.virtual_remote.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)
from homeassistant.components.virtual_remote.diagnostics import (
    async_get_config_entry_diagnostics,
)

from tests.common import MockConfigEntry


async def test_diagnostics(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test config entry diagnostics redacts command payloads."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Virtual Remote",
        data={"unique_id": "secret"},
        options={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: "one",
                    CONF_REMOTE_NAME: "One",
                    CONF_INFRARED_ENTITY_ID: infrared_entity,
                    CONF_REMOTE_COMMANDS: {
                        "POWER": "secret command payload",
                        "MUTE": "another secret",
                    },
                },
                {
                    CONF_REMOTE_ID: "two",
                    CONF_REMOTE_NAME: "Two",
                    CONF_INFRARED_ENTITY_ID: "infrared.missing",
                },
                "bad",
            ]
        },
        unique_id="secret-unique-id",
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["unique_id"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["unique_id"] == "**REDACTED**"
    assert diagnostics["entry"]["options"][CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_COMMANDS] == [
        "MUTE",
        "POWER",
    ]
    assert "secret command payload" not in str(diagnostics)
    assert diagnostics["summary"] == {
        "remote_count": 2,
        "command_count": 2,
        "missing_infrared_entity_count": 1,
    }
    assert diagnostics["virtual_remotes"][0]["infrared_entity_exists"] is True
    assert diagnostics["virtual_remotes"][1]["infrared_entity_exists"] is False


async def test_diagnostics_handles_malformed_options(
    hass: HomeAssistant,
) -> None:
    """Test diagnostics handles malformed option data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Virtual Remote",
        data={},
        options={CONF_VIRTUAL_REMOTES: "bad"},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["virtual_remotes"] == []
    assert diagnostics["summary"]["remote_count"] == 0
