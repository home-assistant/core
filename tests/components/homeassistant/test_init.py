"""The tests for Core components."""

from unittest.mock import Mock, patch

import pytest
import voluptuous as vol
import yaml

from homeassistant import config
from homeassistant.components.homeassistant import (
    ATTR_ENTRY_ID,
    ATTR_SAFE_MODE,
    SERVICE_CHECK_CONFIG,
    SERVICE_HOMEASSISTANT_RESTART,
    SERVICE_HOMEASSISTANT_STOP,
    SERVICE_RELOAD_ALL,
    SERVICE_RELOAD_CORE_CONFIG,
    SERVICE_RELOAD_CUSTOM_TEMPLATES,
    SERVICE_SET_LOCATION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    EVENT_CORE_CONFIG_UPDATE,
    SERVICE_SAVE_PERSISTENT_STATES,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.core as ha
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import entity, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockEntityPlatform,
    MockUser,
    async_capture_events,
    async_mock_service,
    patch_yaml_files,
)


async def test_turn_on_without_entities(hass: HomeAssistant) -> None:
    """Test turn_on method without entities."""
    await async_setup_component(hass, ha.DOMAIN, {})
    calls = async_mock_service(hass, "light", SERVICE_TURN_ON)
    await hass.services.async_call(ha.DOMAIN, SERVICE_TURN_ON, blocking=True)
    assert len(calls) == 0


async def test_turn_on(hass: HomeAssistant) -> None:
    """Test turn_on method."""
    await async_setup_component(hass, ha.DOMAIN, {})
    calls = async_mock_service(hass, "light", SERVICE_TURN_ON)
    await hass.services.async_call(
        ha.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "light.Ceiling"}, blocking=True
    )
    assert len(calls) == 1


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test turn_off method."""
    await async_setup_component(hass, ha.DOMAIN, {})
    calls = async_mock_service(hass, "light", SERVICE_TURN_OFF)
    await hass.services.async_call(
        ha.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "light.Bowl"}, blocking=True
    )
    assert len(calls) == 1


async def test_toggle(hass: HomeAssistant) -> None:
    """Test toggle method."""
    await async_setup_component(hass, ha.DOMAIN, {})
    calls = async_mock_service(hass, "light", SERVICE_TOGGLE)
    await hass.services.async_call(
        ha.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: "light.Bowl"}, blocking=True
    )
    assert len(calls) == 1


@patch("homeassistant.config.os.path.isfile", Mock(return_value=True))
async def test_reload_core_conf(hass: HomeAssistant) -> None:
    """Test reload core conf service."""
    await async_setup_component(hass, ha.DOMAIN, {})
    ent = entity.Entity()
    ent.entity_id = "test.entity"
    ent.hass = hass
    platform = MockEntityPlatform(hass, domain="test", platform_name="test")
    await platform.async_add_entities([ent])
    ent.async_write_ha_state()

    state = hass.states.get("test.entity")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes == {}

    files = {
        config.YAML_CONFIG_FILE: yaml.dump(
            {
                ha.DOMAIN: {
                    "country": "SE",  # To avoid creating issue country_not_configured
                    "latitude": 10,
                    "longitude": 20,
                    "customize": {"test.Entity": {"hello": "world"}},
                }
            }
        )
    }
    with patch_yaml_files(files, True):
        await hass.services.async_call(
            ha.DOMAIN, SERVICE_RELOAD_CORE_CONFIG, blocking=True
        )

    assert hass.config.latitude == 10
    assert hass.config.longitude == 20

    ent.async_write_ha_state()

    state = hass.states.get("test.entity")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes.get("hello") == "world"


@patch("homeassistant.config.os.path.isfile", Mock(return_value=True))
@patch("homeassistant.components.homeassistant._LOGGER.error")
@patch("homeassistant.core_config.async_process_ha_core_config")
async def test_reload_core_with_wrong_conf(
    mock_process, mock_error, hass: HomeAssistant
) -> None:
    """Test reload core conf service."""
    files = {config.YAML_CONFIG_FILE: yaml.dump(["invalid", "config"])}
    await async_setup_component(hass, ha.DOMAIN, {})
    with patch_yaml_files(files, True):
        await hass.services.async_call(
            ha.DOMAIN, SERVICE_RELOAD_CORE_CONFIG, blocking=True
        )

    assert mock_error.called
    assert mock_process.called is False


@patch("homeassistant.core.HomeAssistant.async_stop", return_value=None)
@patch(
    "homeassistant.config.async_check_ha_config_file",
    side_effect=HomeAssistantError("Test error"),
)
async def test_restart_homeassistant_wrong_conf(
    mock_check, mock_restart, hass: HomeAssistant
) -> None:
    """Test restart service with error."""
    await async_setup_component(hass, ha.DOMAIN, {})
    with pytest.raises(HomeAssistantError, match="Test error"):
        await hass.services.async_call(
            ha.DOMAIN, SERVICE_HOMEASSISTANT_RESTART, blocking=True
        )
    assert mock_check.called
    assert not mock_restart.called


@patch("homeassistant.core.HomeAssistant.async_stop", return_value=None)
@patch("homeassistant.config.async_check_ha_config_file", return_value=None)
async def test_check_config(mock_check, mock_stop, hass: HomeAssistant) -> None:
    """Test stop service."""
    await async_setup_component(hass, ha.DOMAIN, {})
    await hass.services.async_call(ha.DOMAIN, SERVICE_CHECK_CONFIG, blocking=True)
    assert mock_check.called
    assert not mock_stop.called


async def test_turn_on_skips_domains_without_service(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if turn_on is blocking domain with no service."""
    await async_setup_component(hass, "homeassistant", {})
    async_mock_service(hass, "light", SERVICE_TURN_ON)
    hass.states.async_set("light.Bowl", STATE_ON)
    hass.states.async_set("light.Ceiling", STATE_OFF)

    # We can't test if our service call results in services being called
    # because by mocking out the call service method, we mock out all
    # So we mimic how the service registry calls services
    service_call = ha.ServiceCall(
        hass,
        "homeassistant",
        "turn_on",
        {"entity_id": ["light.test", "sensor.bla", "binary_sensor.blub", "light.bla"]},
    )
    service = hass.services.async_services_for_domain("homeassistant")["turn_on"]

    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        return_value=None,
    ) as mock_call:
        await service.job.target(service_call)

    assert mock_call.call_count == 1
    assert mock_call.call_args_list[0][0] == (
        "light",
        "turn_on",
        {"entity_id": ["light.bla", "light.test"]},
    )
    assert mock_call.call_args_list[0][1] == {
        "blocking": True,
        "context": service_call.context,
    }
    assert (
        "The service homeassistant.turn_on does not support entities binary_sensor.blub, sensor.bla"
        in caplog.text
    )


async def test_entity_update(hass: HomeAssistant) -> None:
    """Test being able to call entity update."""
    await async_setup_component(hass, "homeassistant", {})

    with patch(
        "homeassistant.components.homeassistant.async_update_entity",
        return_value=None,
    ) as mock_update:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": ["light.kitchen"]},
            blocking=True,
        )

    assert len(mock_update.mock_calls) == 1
    assert mock_update.mock_calls[0][1][1] == "light.kitchen"


async def test_setting_location(hass: HomeAssistant) -> None:
    """Test setting the location."""
    await async_setup_component(hass, "homeassistant", {})
    events = async_capture_events(hass, EVENT_CORE_CONFIG_UPDATE)
    # Just to make sure that we are updating values.
    assert hass.config.latitude != 30
    assert hass.config.longitude != 40
    elevation = hass.config.elevation
    assert elevation != 50
    await hass.services.async_call(
        "homeassistant",
        SERVICE_SET_LOCATION,
        {"latitude": 30, "longitude": 40},
        blocking=True,
    )
    assert len(events) == 1
    assert hass.config.latitude == 30
    assert hass.config.longitude == 40
    assert hass.config.elevation == elevation

    await hass.services.async_call(
        "homeassistant",
        SERVICE_SET_LOCATION,
        {"latitude": 30, "longitude": 40, "elevation": 50},
        blocking=True,
    )
    assert hass.config.latitude == 30
    assert hass.config.longitude == 40
    assert hass.config.elevation == 50

    await hass.services.async_call(
        "homeassistant",
        SERVICE_SET_LOCATION,
        {"latitude": 30, "longitude": 40, "elevation": 0},
        blocking=True,
    )
    assert hass.config.latitude == 30
    assert hass.config.longitude == 40
    assert hass.config.elevation == 0


async def test_require_admin(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Test services requiring admin."""
    await async_setup_component(hass, "homeassistant", {})

    for service in (
        SERVICE_HOMEASSISTANT_RESTART,
        SERVICE_HOMEASSISTANT_STOP,
        SERVICE_CHECK_CONFIG,
        SERVICE_RELOAD_CORE_CONFIG,
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                ha.DOMAIN,
                service,
                {},
                context=ha.Context(user_id=hass_read_only_user.id),
                blocking=True,
            )

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            ha.DOMAIN,
            SERVICE_SET_LOCATION,
            {"latitude": 0, "longitude": 0},
            context=ha.Context(user_id=hass_read_only_user.id),
            blocking=True,
        )


async def test_turn_on_off_toggle_schema(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Test the schemas for the turn on/off/toggle services."""
    await async_setup_component(hass, "homeassistant", {})

    for service in SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE:
        for invalid in None, "nothing", ENTITY_MATCH_ALL, ENTITY_MATCH_NONE:
            with pytest.raises(vol.Invalid):
                await hass.services.async_call(
                    ha.DOMAIN,
                    service,
                    {"entity_id": invalid},
                    context=ha.Context(user_id=hass_read_only_user.id),
                    blocking=True,
                )


async def test_not_allowing_recursion(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we do not allow recursion."""
    await async_setup_component(hass, "homeassistant", {})

    for service in SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE:
        await hass.services.async_call(
            ha.DOMAIN,
            service,
            {"entity_id": "homeassistant.light"},
            blocking=True,
        )
        assert (
            f"Called service homeassistant.{service} with invalid entities homeassistant.light"
            in caplog.text
        ), service


async def test_reload_config_entry_by_entity_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test being able to reload a config entry by entity_id."""
    await async_setup_component(hass, "homeassistant", {})
    entry1 = MockConfigEntry(domain="mockdomain")
    entry1.add_to_hass(hass)
    entry2 = MockConfigEntry(domain="mockdomain")
    entry2.add_to_hass(hass)
    reg_entity1 = entity_registry.async_get_or_create(
        "binary_sensor", "powerwall", "battery_charging", config_entry=entry1
    )
    reg_entity2 = entity_registry.async_get_or_create(
        "binary_sensor", "powerwall", "battery_status", config_entry=entry2
    )
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
        return_value=None,
    ) as mock_reload:
        await hass.services.async_call(
            "homeassistant",
            "reload_config_entry",
            {"entity_id": f"{reg_entity1.entity_id},{reg_entity2.entity_id}"},
            blocking=True,
        )

    assert len(mock_reload.mock_calls) == 2
    assert {mock_reload.mock_calls[0][1][0], mock_reload.mock_calls[1][1][0]} == {
        entry1.entry_id,
        entry2.entry_id,
    }

    with pytest.raises(ValueError):
        await hass.services.async_call(
            "homeassistant",
            "reload_config_entry",
            {"entity_id": "unknown.entity_id"},
            blocking=True,
        )


async def test_reload_config_entry_by_entry_id(hass: HomeAssistant) -> None:
    """Test being able to reload a config entry by config entry id."""
    await async_setup_component(hass, "homeassistant", {})

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
        return_value=None,
    ) as mock_reload:
        await hass.services.async_call(
            "homeassistant",
            "reload_config_entry",
            {ATTR_ENTRY_ID: "8955375327824e14ba89e4b29cc3ec9a"},
            blocking=True,
        )

    assert len(mock_reload.mock_calls) == 1
    assert mock_reload.mock_calls[0][1][0] == "8955375327824e14ba89e4b29cc3ec9a"


@pytest.mark.parametrize(
    "service", [SERVICE_HOMEASSISTANT_RESTART, SERVICE_HOMEASSISTANT_STOP]
)
async def test_raises_when_db_upgrade_in_progress(
    hass: HomeAssistant, service, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an exception is raised when the database migration is in progress."""
    await async_setup_component(hass, "homeassistant", {})

    with (
        pytest.raises(HomeAssistantError),
        patch(
            "homeassistant.helpers.recorder.async_migration_in_progress",
            return_value=True,
        ) as mock_async_migration_in_progress,
    ):
        await hass.services.async_call(
            "homeassistant",
            service,
            blocking=True,
        )
    assert "The system cannot" in caplog.text
    assert "while a database upgrade is in progress" in caplog.text

    assert mock_async_migration_in_progress.called
    caplog.clear()

    with (
        patch(
            "homeassistant.helpers.recorder.async_migration_in_progress",
            return_value=False,
        ) as mock_async_migration_in_progress,
        patch("homeassistant.config.async_check_ha_config_file", return_value=None),
    ):
        await hass.services.async_call(
            "homeassistant",
            service,
            blocking=True,
        )
        assert "The system cannot" not in caplog.text
        assert "while a database upgrade in progress" not in caplog.text

    assert mock_async_migration_in_progress.called


async def test_raises_when_config_is_invalid(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an exception is raised when the configuration is invalid."""
    await async_setup_component(hass, "homeassistant", {})

    with (
        pytest.raises(HomeAssistantError),
        patch(
            "homeassistant.helpers.recorder.async_migration_in_progress",
            return_value=False,
        ),
        patch(
            "homeassistant.config.async_check_ha_config_file", return_value=["Error 1"]
        ) as mock_async_check_ha_config_file,
    ):
        await hass.services.async_call(
            "homeassistant",
            SERVICE_HOMEASSISTANT_RESTART,
            blocking=True,
        )
    assert "The system cannot" in caplog.text
    assert "because the configuration is not valid" in caplog.text
    assert "Error 1" in caplog.text

    assert mock_async_check_ha_config_file.called
    caplog.clear()

    with (
        patch(
            "homeassistant.helpers.recorder.async_migration_in_progress",
            return_value=False,
        ),
        patch(
            "homeassistant.config.async_check_ha_config_file", return_value=None
        ) as mock_async_check_ha_config_file,
    ):
        await hass.services.async_call(
            "homeassistant",
            SERVICE_HOMEASSISTANT_RESTART,
            blocking=True,
        )

    assert mock_async_check_ha_config_file.called


@pytest.mark.parametrize(
    ("service_data", "safe_mode_enabled"),
    [({}, False), ({ATTR_SAFE_MODE: False}, False), ({ATTR_SAFE_MODE: True}, True)],
)
async def test_restart_homeassistant(
    hass: HomeAssistant, service_data: dict, safe_mode_enabled: bool
) -> None:
    """Test we can restart when there is no configuration error."""
    await async_setup_component(hass, "homeassistant", {})
    with (
        patch(
            "homeassistant.config.async_check_ha_config_file", return_value=None
        ) as mock_check,
        patch("homeassistant.config.async_enable_safe_mode") as mock_safe_mode,
        patch(
            "homeassistant.core.HomeAssistant.async_stop", return_value=None
        ) as mock_restart,
    ):
        await hass.services.async_call(
            "homeassistant",
            SERVICE_HOMEASSISTANT_RESTART,
            service_data,
            blocking=True,
        )
        assert mock_check.called
        await hass.async_block_till_done()
        assert mock_restart.called
        assert mock_safe_mode.called == safe_mode_enabled


async def test_stop_homeassistant(hass: HomeAssistant) -> None:
    """Test we can stop when there is a configuration error."""
    await async_setup_component(hass, "homeassistant", {})
    with (
        patch(
            "homeassistant.config.async_check_ha_config_file", return_value=None
        ) as mock_check,
        patch(
            "homeassistant.core.HomeAssistant.async_stop", return_value=None
        ) as mock_restart,
    ):
        await hass.services.async_call(
            "homeassistant",
            SERVICE_HOMEASSISTANT_STOP,
            blocking=True,
        )
        assert not mock_check.called
        await hass.async_block_till_done()
        assert mock_restart.called


async def test_save_persistent_states(hass: HomeAssistant) -> None:
    """Test we can call save_persistent_states."""
    await async_setup_component(hass, "homeassistant", {})
    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_save_persistent_states",
        return_value=None,
    ) as mock_save:
        await hass.services.async_call(
            "homeassistant",
            SERVICE_SAVE_PERSISTENT_STATES,
            blocking=True,
        )
        assert mock_save.called


async def test_reload_custom_templates(hass: HomeAssistant) -> None:
    """Test we can call reload_custom_templates."""
    await async_setup_component(hass, "homeassistant", {})
    with patch(
        "homeassistant.components.homeassistant.async_load_custom_templates",
        return_value=None,
    ) as mock_load_custom_templates:
        await hass.services.async_call(
            "homeassistant",
            SERVICE_RELOAD_CUSTOM_TEMPLATES,
            blocking=True,
        )
        assert mock_load_custom_templates.called


async def test_reload_all(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reload_all service."""
    await async_setup_component(hass, "homeassistant", {})
    test1 = async_mock_service(hass, "test1", "reload")
    test2 = async_mock_service(hass, "test2", "reload")
    no_reload = async_mock_service(hass, "test3", "not_reload")
    notify = async_mock_service(hass, "notify", "reload")
    core_config = async_mock_service(hass, "homeassistant", "reload_core_config")
    themes = async_mock_service(hass, "frontend", "reload_themes")
    jinja = async_mock_service(hass, "homeassistant", "reload_custom_templates")

    with patch(
        "homeassistant.config.async_check_ha_config_file",
        return_value=None,
    ) as mock_async_check_ha_config_file:
        await hass.services.async_call(
            "homeassistant",
            SERVICE_RELOAD_ALL,
            blocking=True,
        )

    assert mock_async_check_ha_config_file.called
    assert len(test1) == 1
    assert len(test2) == 1
    assert len(no_reload) == 0
    assert len(notify) == 0
    assert len(core_config) == 1
    assert len(themes) == 1

    with (
        pytest.raises(
            HomeAssistantError,
            match=(
                "Cannot quick reload all YAML configurations because the configuration is "
                "not valid: Oh no, drama!"
            ),
        ),
        patch(
            "homeassistant.config.async_check_ha_config_file",
            return_value="Oh no, drama!",
        ) as mock_async_check_ha_config_file,
    ):
        await hass.services.async_call(
            "homeassistant",
            SERVICE_RELOAD_ALL,
            blocking=True,
        )

    assert mock_async_check_ha_config_file.called
    assert (
        "The system cannot reload because the configuration is not valid: Oh no, drama!"
        in caplog.text
    )

    # None have been called again
    assert len(test1) == 1
    assert len(test2) == 1
    assert len(core_config) == 1
    assert len(themes) == 1
    assert len(jinja) == 1
