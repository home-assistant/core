"""Test KNX entity unique_id generation and migration."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from xknx.telegram.address import GroupAddress, GroupAddressType, InternalGroupAddress

from homeassistant.components.knx.const import DOMAIN, KNX_ADDRESS
from homeassistant.components.knx.entity import build_yaml_unique_id
from homeassistant.components.knx.schema import LightSchema, SwitchSchema
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import KNXTestKit


@pytest.fixture
def two_level_address_format() -> Generator[None]:
    """Force the global group address format to 2-level (SHORT)."""
    with patch(
        "homeassistant.components.knx.project.KNXProject.get_address_format",
        return_value=GroupAddressType.SHORT,
    ):
        yield


@pytest.mark.parametrize(
    "address_format",
    [GroupAddressType.LONG, GroupAddressType.SHORT, GroupAddressType.FREE],
)
def test_build_yaml_unique_id_is_format_independent(
    monkeypatch: pytest.MonkeyPatch, address_format: GroupAddressType
) -> None:
    """The stable unique_id is always the LONG form regardless of global format."""
    monkeypatch.setattr(GroupAddress, "address_format", address_format)
    new_id, _legacy_id = build_yaml_unique_id(GroupAddress("1/2/3"))
    assert new_id == "1/2/3"


def test_build_yaml_unique_id_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Composite ids keep non-address parts and legacy ids follow the global format."""
    monkeypatch.setattr(GroupAddress, "address_format", GroupAddressType.SHORT)
    new_id, legacy_id = build_yaml_unique_id(
        GroupAddress("1/2/3"), None, InternalGroupAddress("i-foo"), 24
    )
    assert new_id == "1/2/3_None_i-foo_24"
    assert legacy_id == "1/515_None_i-foo_24"


@pytest.mark.usefixtures("two_level_address_format")
async def test_yaml_unique_id_stable_with_two_level_style(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """A 2-level style install still gets the LONG unique_id, not the 2-level string."""
    await knx.setup_integration(
        {SwitchSchema.PLATFORM: {CONF_NAME: "test", KNX_ADDRESS: "1/2/3"}}
    )
    entry = entity_registry.async_get("switch.test")
    assert entry
    assert entry.unique_id == "1/2/3"


@pytest.mark.usefixtures("two_level_address_format")
async def test_yaml_unique_id_migration(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """A legacy (2-level) unique_id is migrated to the stable LONG form."""
    legacy_unique_id = "1/515"
    knx.mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        object_id_base="test",
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=legacy_unique_id,
        config_entry=knx.mock_config_entry,
    )
    await knx.setup_integration(
        {SwitchSchema.PLATFORM: {CONF_NAME: "test", KNX_ADDRESS: "1/2/3"}},
        add_entry_to_hass=False,
    )
    entry = entity_registry.async_get("switch.test")
    assert entry
    assert entry.unique_id == "1/2/3"
    assert not entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, legacy_unique_id
    )


@pytest.mark.usefixtures("two_level_address_format")
async def test_yaml_unique_id_migration_collision(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """A stale legacy entry is removed when the stable unique_id already exists."""
    legacy_unique_id = "1/515"
    new_unique_id = "1/2/3"
    knx.mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=new_unique_id,
        config_entry=knx.mock_config_entry,
    )
    legacy_entry = entity_registry.async_get_or_create(
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=legacy_unique_id,
        config_entry=knx.mock_config_entry,
    )
    await knx.setup_integration(
        {SwitchSchema.PLATFORM: {CONF_NAME: "test", KNX_ADDRESS: "1/2/3"}},
        add_entry_to_hass=False,
    )
    assert entity_registry.async_get_entity_id(Platform.SWITCH, DOMAIN, new_unique_id)
    assert not entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, legacy_unique_id
    )
    assert entity_registry.async_get(legacy_entry.entity_id) is None


async def test_yaml_user_unique_id(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """A user-defined unique_id is used verbatim instead of the derived one."""
    await knx.setup_integration(
        {
            SwitchSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
                CONF_UNIQUE_ID: "my_switch",
            }
        }
    )
    entry = entity_registry.async_get("switch.test")
    assert entry
    assert entry.unique_id == "my_switch"


async def test_yaml_user_unique_id_migration(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """Adding a user-defined unique_id migrates the auto-generated entity to it."""
    auto_unique_id = "1/2/3"
    knx.mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        object_id_base="test",
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=auto_unique_id,
        config_entry=knx.mock_config_entry,
    )
    await knx.setup_integration(
        {
            SwitchSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
                CONF_UNIQUE_ID: "my_switch",
            }
        },
        add_entry_to_hass=False,
    )
    entry = entity_registry.async_get("switch.test")
    assert entry
    assert entry.unique_id == "my_switch"
    assert not entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, auto_unique_id
    )


@pytest.mark.usefixtures("two_level_address_format")
async def test_yaml_user_unique_id_migration_from_legacy(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """A user-defined unique_id migrates even from the legacy (2-level) id."""
    legacy_unique_id = "1/515"
    knx.mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        object_id_base="test",
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=legacy_unique_id,
        config_entry=knx.mock_config_entry,
    )
    await knx.setup_integration(
        {
            SwitchSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
                CONF_UNIQUE_ID: "my_switch",
            }
        },
        add_entry_to_hass=False,
    )
    entry = entity_registry.async_get("switch.test")
    assert entry
    assert entry.unique_id == "my_switch"
    assert not entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, legacy_unique_id
    )
    assert not entity_registry.async_get_entity_id(Platform.SWITCH, DOMAIN, "1/2/3")


async def test_yaml_user_unique_id_shared_across_platforms(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """The same user unique_id is allowed on entities of different platforms."""
    await knx.setup_integration(
        {
            SwitchSchema.PLATFORM: {
                CONF_NAME: "sw",
                KNX_ADDRESS: "1/2/3",
                CONF_UNIQUE_ID: "shared",
            },
            LightSchema.PLATFORM: {
                CONF_NAME: "li",
                KNX_ADDRESS: "1/2/4",
                CONF_UNIQUE_ID: "shared",
            },
        }
    )
    switch_entry = entity_registry.async_get("switch.sw")
    light_entry = entity_registry.async_get("light.li")
    assert switch_entry and switch_entry.unique_id == "shared"
    assert light_entry and light_entry.unique_id == "shared"


async def test_yaml_duplicate_user_unique_id_invalid(
    hass: HomeAssistant, knx: KNXTestKit, caplog: pytest.LogCaptureFixture
) -> None:
    """Two entities of the same platform must not share a user unique_id."""
    await knx.setup_integration(
        {
            SwitchSchema.PLATFORM: [
                {CONF_NAME: "a", KNX_ADDRESS: "1/2/3", CONF_UNIQUE_ID: "dup"},
                {CONF_NAME: "b", KNX_ADDRESS: "1/2/4", CONF_UNIQUE_ID: "dup"},
            ]
        }
    )
    assert "duplicate 'unique_id' not allowed: dup" in caplog.text
    assert hass.states.get("switch.a") is None


async def test_yaml_user_unique_id_collision_keeps_generated_id(
    hass: HomeAssistant,
    knx: KNXTestKit,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A user id colliding with another entity keeps the generated id, no deletion."""
    knx.mock_config_entry.add_to_hass(hass)
    # another entity already owns the id the user configures below
    entity_registry.async_get_or_create(
        object_id_base="other",
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id="taken",
        config_entry=knx.mock_config_entry,
    )
    # the entity being configured already exists under its generated id
    generated_entry = entity_registry.async_get_or_create(
        object_id_base="test",
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id="1/2/3",
        config_entry=knx.mock_config_entry,
    )
    await knx.setup_integration(
        {
            SwitchSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
                CONF_UNIQUE_ID: "taken",
            }
        },
        add_entry_to_hass=False,
    )
    # the generated entry is untouched (history preserved), user id not adopted
    assert entity_registry.async_get(generated_entry.entity_id) is not None
    entry = entity_registry.async_get(generated_entry.entity_id)
    assert entry.unique_id == "1/2/3"
    # the other entity keeps ownership of the configured id
    assert (
        entity_registry.async_get_entity_id(Platform.SWITCH, DOMAIN, "taken")
        != generated_entry.entity_id
    )
    assert "already in use" in caplog.text
