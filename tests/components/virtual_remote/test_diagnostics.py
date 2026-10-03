"""Tests for Virtual Remote diagnostics."""

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
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

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
                {
                    CONF_REMOTE_ID: "three",
                    CONF_REMOTE_NAME: "Three",
                    CONF_INFRARED_ENTITY_ID: "infrared.unavailable",
                },
                "bad",
            ]
        },
        unique_id="secret-unique-id",
    )
    entry.add_to_hass(hass)
    hass.states.async_set("infrared.unavailable", STATE_UNAVAILABLE)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["unique_id"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["unique_id"] == "**REDACTED**"
    assert diagnostics["entry"]["options"][CONF_VIRTUAL_REMOTES][0][
        CONF_REMOTE_COMMANDS
    ] == [
        "MUTE",
        "POWER",
    ]
    assert "secret command payload" not in str(diagnostics)
    assert diagnostics["summary"] == {
        "remote_count": 3,
        "command_count": 2,
        "missing_infrared_entity_count": 2,
    }
    assert diagnostics["virtual_remotes"][0]["infrared_entity_exists"] is True
    assert diagnostics["virtual_remotes"][1]["infrared_entity_exists"] is False
    assert diagnostics["virtual_remotes"][2]["infrared_entity_exists"] is False


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
    hass.states.async_set("infrared.unavailable", STATE_UNAVAILABLE)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["virtual_remotes"] == []
    assert diagnostics["summary"]["remote_count"] == 0


async def test_diagnostics_supports_single_entry_remote(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test diagnostics supports one virtual remote per config entry storage."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="TV",
        data={
            CONF_REMOTE_ID: "tv",
            CONF_REMOTE_NAME: "TV",
            CONF_INFRARED_ENTITY_ID: infrared_entity,
        },
        options={CONF_REMOTE_COMMANDS: {"POWER_ON": "38000:1,2"}},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["summary"] == {
        "remote_count": 1,
        "command_count": 1,
        "missing_infrared_entity_count": 0,
    }
    assert diagnostics["virtual_remote"] == {
        "id": "tv",
        "name": "TV",
        "infrared_entity_id": infrared_entity,
        "infrared_entity_exists": True,
        "command_count": 1,
        "commands": ["POWER_ON"],
    }
    assert "virtual_remotes" not in diagnostics


async def test_diagnostics_legacy_multi_remote_storage(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics preserve legacy multi-remote structure."""
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    assert "virtual_remotes" in diagnostics
    assert isinstance(diagnostics["virtual_remotes"], list)
    assert "virtual_remote" not in diagnostics
