"""The tests for the Template update platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import template, update
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_ICON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    ConfigurationStyle,
    async_get_flow_preview_state,
    async_setup_modern_state_format,
    async_setup_modern_trigger_format,
    make_test_trigger,
)

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    mock_restore_cache_with_extra_data,
)
from tests.conftest import WebSocketGenerator

TEST_OBJECT_ID = "template_update"
TEST_ENTITY_ID = f"update.{TEST_OBJECT_ID}"
TEST_INSTALLED_SENSOR = "sensor.installed_update"
TEST_LATEST_SENSOR = "sensor.latest_update"
TEST_SENSOR_ID = "sensor.test_update"
TEST_STATE_TRIGGER = make_test_trigger(
    TEST_INSTALLED_SENSOR, TEST_LATEST_SENSOR, TEST_SENSOR_ID
)
TEST_INSTALLED_TEMPLATE = "{{ '1.0' }}"
TEST_LATEST_TEMPLATE = "{{ '2.0' }}"

TEST_UPDATE_CONFIG = {
    "installed_version": TEST_INSTALLED_TEMPLATE,
    "latest_version": TEST_LATEST_TEMPLATE,
}
TEST_UNIQUE_ID_CONFIG = {
    **TEST_UPDATE_CONFIG,
    "unique_id": "not-so-unique-anymore",
}

INSTALL_ACTION = {
    "install": {
        "action": "test.automation",
        "data": {
            "caller": "{{ this.entity_id }}",
            "action": "install",
            "backup": "{{ backup }}",
            "specific_version": "{{ specific_version }}",
        },
    }
}


async def async_setup_config(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: dict[str, Any],
    extra_config: dict[str, Any] | None,
) -> None:
    """Do setup of update integration."""
    config = {**config, **extra_config} if extra_config else config
    if style == ConfigurationStyle.MODERN:
        await async_setup_modern_state_format(hass, update.DOMAIN, count, config)
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_modern_trigger_format(
            hass, update.DOMAIN, TEST_STATE_TRIGGER, count, config
        )


@pytest.fixture
async def setup_base(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: dict[str, Any],
) -> None:
    """Do setup of update integration."""
    await async_setup_config(
        hass,
        count,
        style,
        config,
        None,
    )


@pytest.fixture
async def setup_update(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    installed_template: str,
    latest_template: str,
    extra_config: dict[str, Any] | None,
) -> None:
    """Do setup of update integration."""
    await async_setup_config(
        hass,
        count,
        style,
        {
            "name": TEST_OBJECT_ID,
            "installed_version": installed_template,
            "latest_version": latest_template,
        },
        extra_config,
    )


@pytest.fixture
async def setup_single_attribute_update(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    installed_template: str,
    latest_template: str,
    attribute: str,
    attribute_template: str,
) -> None:
    """Do setup of update platform testing a single attribute."""
    await async_setup_config(
        hass,
        1,
        style,
        {
            "name": TEST_OBJECT_ID,
            "installed_version": installed_template,
            "latest_version": latest_template,
        },
        {attribute: attribute_template} if attribute and attribute_template else {},
    )


async def test_legacy_platform_config(hass: HomeAssistant) -> None:
    """Test a legacy platform does not create update entities."""
    with assert_setup_component(1, update.DOMAIN):
        assert await async_setup_component(
            hass,
            update.DOMAIN,
            {"update": {"platform": "template", "updates": {TEST_OBJECT_ID: {}}}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
    assert hass.states.async_all("update") == []


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the config flow."""

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": TEST_OBJECT_ID,
            "template_type": update.DOMAIN,
            **TEST_UPDATE_CONFIG,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state == snapshot


async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for device for Template."""

    device_config_entry = MockConfigEntry()
    device_config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=device_config_entry.entry_id,
        identifiers={("test", "identifier_test")},
        connections={("mac", "30:31:32:33:34:35")},
    )
    await hass.async_block_till_done()
    assert device_entry is not None
    assert device_entry.id is not None

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": TEST_OBJECT_ID,
            "template_type": update.DOMAIN,
            **TEST_UPDATE_CONFIG,
            "device_id": device_entry.id,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get(TEST_ENTITY_ID)
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id


@pytest.mark.parametrize(("count", "extra_config"), [(1, None)])
@pytest.mark.parametrize(
    ("style", "expected_state"),
    [
        (ConfigurationStyle.MODERN, STATE_UNKNOWN),
        (ConfigurationStyle.TRIGGER, STATE_UNKNOWN),
    ],
)
@pytest.mark.parametrize(
    ("installed_template", "latest_template"),
    [
        ("{{states.test['big.fat...']}}", TEST_LATEST_TEMPLATE),
        (TEST_INSTALLED_TEMPLATE, "{{states.test['big.fat...']}}"),
        ("{{states.test['big.fat...']}}", "{{states.test['big.fat...']}}"),
    ],
)
@pytest.mark.usefixtures("setup_update")
async def test_syntax_error(
    hass: HomeAssistant,
    expected_state: str,
) -> None:
    """Test template update with render error."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("count", "extra_config", "installed_template", "latest_template"),
    [
        (
            1,
            None,
            "{{ states('sensor.installed_update') }}",
            "{{ states('sensor.latest_update') }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("installed", "latest", "expected"),
    [
        ("1.0", "2.0", STATE_ON),
        ("2.0", "2.0", STATE_OFF),
    ],
)
@pytest.mark.usefixtures("setup_update")
async def test_update_templates(
    hass: HomeAssistant, installed: str, latest: str, expected: str
) -> None:
    """Test update template."""
    hass.states.async_set(TEST_INSTALLED_SENSOR, installed)
    hass.states.async_set(TEST_LATEST_SENSOR, latest)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == expected
    assert state.attributes["installed_version"] == installed
    assert state.attributes["latest_version"] == latest

    # ensure that the entity picture exists when not provided.
    assert (
        state.attributes["entity_picture"]
        == "https://brands.home-assistant.io/_/template/icon.png"
    )


@pytest.mark.parametrize(
    ("count", "extra_config", "installed_template", "latest_template"),
    [
        (
            1,
            None,
            "{{ states('sensor.installed_update') }}",
            "{{ states('sensor.latest_update') }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_update")
async def test_installed_and_latest_template_updates_from_entity(
    hass: HomeAssistant,
) -> None:
    """Test template installed and latest version templates updates from entities."""
    hass.states.async_set(TEST_INSTALLED_SENSOR, "1.0")
    hass.states.async_set(TEST_LATEST_SENSOR, "2.0")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["installed_version"] == "1.0"
    assert state.attributes["latest_version"] == "2.0"

    hass.states.async_set(TEST_INSTALLED_SENSOR, "2.0")
    hass.states.async_set(TEST_LATEST_SENSOR, "2.0")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["installed_version"] == "2.0"
    assert state.attributes["latest_version"] == "2.0"

    hass.states.async_set(TEST_INSTALLED_SENSOR, "2.0")
    hass.states.async_set(TEST_LATEST_SENSOR, "3.0")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["installed_version"] == "2.0"
    assert state.attributes["latest_version"] == "3.0"


@pytest.mark.parametrize(
    ("count", "extra_config", "latest_template"),
    [(1, None, TEST_LATEST_TEMPLATE)],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("installed_template", "expected", "expected_attr"),
    [
        ("{{ '1.0' }}", STATE_ON, "1.0"),
        ("{{ 1.0 }}", STATE_ON, "1.0"),
        ("{{ '2.0' }}", STATE_OFF, "2.0"),
        ("{{ 2.0 }}", STATE_OFF, "2.0"),
        ("{{ None }}", STATE_UNKNOWN, None),
        ("{{ 'foo' }}", STATE_ON, "foo"),
        ("{{ x + 2 }}", STATE_UNKNOWN, None),
    ],
)
@pytest.mark.usefixtures("setup_update")
async def test_installed_version_template(
    hass: HomeAssistant, expected: str, expected_attr: Any
) -> None:
    """Test installed_version template results."""
    # Ensure trigger based template entities update
    hass.states.async_set(TEST_INSTALLED_SENSOR, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == expected
    assert state.attributes["installed_version"] == expected_attr


@pytest.mark.parametrize(
    ("count", "extra_config", "installed_template"),
    [(1, None, TEST_INSTALLED_TEMPLATE)],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("latest_template", "expected", "expected_attr"),
    [
        ("{{ '1.0' }}", STATE_OFF, "1.0"),
        ("{{ 1.0 }}", STATE_OFF, "1.0"),
        ("{{ '2.0' }}", STATE_ON, "2.0"),
        ("{{ 2.0 }}", STATE_ON, "2.0"),
        ("{{ None }}", STATE_UNKNOWN, None),
        ("{{ 'foo' }}", STATE_ON, "foo"),
        ("{{ x + 2 }}", STATE_UNKNOWN, None),
    ],
)
@pytest.mark.usefixtures("setup_update")
async def test_latest_version_template(
    hass: HomeAssistant, expected: str, expected_attr: Any
) -> None:
    """Test latest_version template results."""
    # Ensure trigger based template entities update
    hass.states.async_set(TEST_INSTALLED_SENSOR, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == expected
    assert state.attributes["latest_version"] == expected_attr


@pytest.mark.parametrize(
    ("count", "extra_config", "installed_template", "latest_template"),
    [
        (
            1,
            INSTALL_ACTION,
            "{{ states('sensor.installed_update') }}",
            "{{ states('sensor.latest_update') }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_update")
async def test_install_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test install action."""

    hass.states.async_set(TEST_INSTALLED_SENSOR, "1.0")
    hass.states.async_set(TEST_LATEST_SENSOR, "2.0")
    await hass.async_block_till_done()

    await hass.services.async_call(
        update.DOMAIN,
        update.SERVICE_INSTALL,
        {"entity_id": TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    # verify
    assert len(calls) == 1
    assert calls[-1].data["action"] == "install"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID

    hass.states.async_set(TEST_INSTALLED_SENSOR, "2.0")
    hass.states.async_set(TEST_LATEST_SENSOR, "2.0")
    await hass.async_block_till_done()

    # Ensure an error is raised when there's no update.
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            update.DOMAIN,
            update.SERVICE_INSTALL,
            {"entity_id": TEST_ENTITY_ID},
            blocking=True,
        )
    await hass.async_block_till_done()

    # verify
    assert len(calls) == 1
    assert calls[-1].data["action"] == "install"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


@pytest.mark.parametrize(
    ("installed_template", "latest_template"),
    [(TEST_INSTALLED_TEMPLATE, TEST_LATEST_TEMPLATE)],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("attribute", "attribute_template", "key", "expected"),
    [
        (
            "picture",
            "{% if is_state('sensor.installed_update', 'on') %}something{% endif %}",
            ATTR_ENTITY_PICTURE,
            "something",
        ),
        (
            "icon",
            "{% if is_state('sensor.installed_update', 'on') %}mdi:something{% endif %}",
            ATTR_ICON,
            "mdi:something",
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_update")
async def test_entity_picture_and_icon_templates(
    hass: HomeAssistant, key: str, expected: str
) -> None:
    """Test picture and icon template."""
    state = hass.states.async_set(TEST_INSTALLED_SENSOR, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(key) in ("", None)

    state = hass.states.async_set(TEST_INSTALLED_SENSOR, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)

    assert state.attributes[key] == expected


@pytest.mark.parametrize(
    ("installed_template", "latest_template"),
    [(TEST_INSTALLED_TEMPLATE, TEST_LATEST_TEMPLATE)],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("attribute", "attribute_template"),
    [
        (
            "picture",
            "{{ 'foo.png' if is_state('sensor.installed_update', 'on') else None }}",
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_update")
async def test_entity_picture_uses_default(hass: HomeAssistant) -> None:
    """Test entity picture when template resolves None."""
    state = hass.states.async_set(TEST_INSTALLED_SENSOR, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes[ATTR_ENTITY_PICTURE] == "foo.png"

    state = hass.states.async_set(TEST_INSTALLED_SENSOR, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)

    assert (
        state.attributes[ATTR_ENTITY_PICTURE]
        == "https://brands.home-assistant.io/_/template/icon.png"
    )


@pytest.mark.parametrize(
    ("installed_template", "latest_template", "attribute"),
    [(TEST_INSTALLED_TEMPLATE, TEST_LATEST_TEMPLATE, "in_progress")],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("attribute_template", "expected", "error"),
    [
        ("{{ True }}", True, None),
        ("{{ False }}", False, None),
        ("{{ None }}", False, "Received invalid in_process value: None"),
        (
            "{{ 'foo' }}",
            False,
            "Received invalid in_process value: foo",
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_update")
async def test_in_process_template(
    hass: HomeAssistant,
    attribute: str,
    expected: Any,
    error: str | None,
    caplog: pytest.LogCaptureFixture,
    caplog_setup_text: str,
) -> None:
    """Test in process templates."""
    # Ensure trigger entities trigger.
    state = hass.states.async_set(TEST_INSTALLED_SENSOR, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(attribute) == expected

    assert error is None or error in caplog_setup_text or error in caplog.text


@pytest.mark.parametrize(
    (
        "installed_template",
        "latest_template",
    ),
    [(TEST_INSTALLED_TEMPLATE, TEST_LATEST_TEMPLATE)],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize("attribute", ["release_summary", "title"])
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ True }}", "True"),
        ("{{ False }}", "False"),
        ("{{ None }}", None),
        ("{{ 'foo' }}", "foo"),
        ("{{ 1.0 }}", "1.0"),
        ("{{ x + 2 }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_update")
async def test_release_summary_and_title_templates(
    hass: HomeAssistant,
    attribute: str,
    expected: Any,
) -> None:
    """Test release summary and title templates."""
    # Ensure trigger entities trigger.
    state = hass.states.async_set(TEST_INSTALLED_SENSOR, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(attribute) == expected


@pytest.mark.parametrize(
    ("installed_template", "latest_template", "attribute"),
    [(TEST_INSTALLED_TEMPLATE, TEST_LATEST_TEMPLATE, "release_url")],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("attribute_template", "expected", "error"),
    [
        ("{{ 'http://foo.bar' }}", "http://foo.bar", None),
        ("{{ 'https://foo.bar' }}", "https://foo.bar", None),
        ("{{ None }}", None, None),
        (
            "{{ '/local/thing' }}",
            None,
            "Received invalid release_url: /local/thing",
        ),
        (
            "{{ 'foo' }}",
            None,
            "Received invalid release_url: foo",
        ),
        (
            "{{ 1.0 }}",
            None,
            "Received invalid release_url: 1",
        ),
        (
            "{{ True }}",
            None,
            "Received invalid release_url: True",
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_update")
async def test_release_url_template(
    hass: HomeAssistant,
    attribute: str,
    expected: Any,
    error: str | None,
    caplog: pytest.LogCaptureFixture,
    caplog_setup_text: str,
) -> None:
    """Test release url templates."""
    # Ensure trigger entities trigger.
    state = hass.states.async_set(TEST_INSTALLED_SENSOR, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(attribute) == expected

    assert error is None or error in caplog_setup_text or error in caplog.text


@pytest.mark.parametrize(
    ("installed_template", "latest_template", "attribute"),
    [(TEST_INSTALLED_TEMPLATE, TEST_LATEST_TEMPLATE, "update_percentage")],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("attribute_template", "expected", "error"),
    [
        ("{{ 100 }}", 100, None),
        ("{{ 0 }}", 0, None),
        ("{{ 45 }}", 45, None),
        ("{{ None }}", None, None),
        ("{{ -1 }}", None, "Received invalid update_percentage: -1"),
        ("{{ 101 }}", None, "Received invalid update_percentage: 101"),
        ("{{ 'foo' }}", None, "Received invalid update_percentage: foo"),
        ("{{ x - 4 }}", None, "UndefinedError: 'x' is undefined"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_update")
async def test_update_percent_template(
    hass: HomeAssistant,
    attribute: str,
    expected: Any,
    error: str | None,
    caplog: pytest.LogCaptureFixture,
    caplog_setup_text: str,
) -> None:
    """Test update percent templates."""
    # Ensure trigger entities trigger.
    state = hass.states.async_set(TEST_INSTALLED_SENSOR, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get(attribute) == expected

    assert error is None or error in caplog_setup_text or error in caplog.text


@pytest.mark.parametrize(
    ("installed_template", "latest_template", "attribute", "attribute_template"),
    [
        (
            TEST_INSTALLED_TEMPLATE,
            TEST_LATEST_TEMPLATE,
            "update_percentage",
            "{% set e = 'sensor.test_update' %}{{ states(e) if e | has_value else None }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_single_attribute_update")
async def test_optimistic_in_progress_with_update_percent_template(
    hass: HomeAssistant,
) -> None:
    """Test optimistic in_progress attribute with update percent templates."""
    # Ensure trigger entities trigger.
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["in_progress"] is False
    assert state.attributes["update_percentage"] is None

    for i in range(101):
        state = hass.states.async_set(TEST_SENSOR_ID, i)
        await hass.async_block_till_done()

        state = hass.states.get(TEST_ENTITY_ID)
        assert state.attributes["in_progress"] is True
        assert state.attributes["update_percentage"] == i

    state = hass.states.async_set(TEST_SENSOR_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["in_progress"] is False
    assert state.attributes["update_percentage"] is None


@pytest.mark.parametrize(
    (
        "count",
        "installed_template",
        "latest_template",
    ),
    [(1, TEST_INSTALLED_TEMPLATE, TEST_LATEST_TEMPLATE)],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    (
        "extra_config",
        "supported_feature",
        "action_data",
        "expected_backup",
        "expected_version",
    ),
    [
        (
            {"backup": True, **INSTALL_ACTION},
            update.UpdateEntityFeature.BACKUP | update.UpdateEntityFeature.INSTALL,
            {"backup": True},
            True,
            None,
        ),
        (
            {"specific_version": True, **INSTALL_ACTION},
            update.UpdateEntityFeature.SPECIFIC_VERSION
            | update.UpdateEntityFeature.INSTALL,
            {"version": "v2.0"},
            False,
            "v2.0",
        ),
        (
            {"backup": True, "specific_version": True, **INSTALL_ACTION},
            update.UpdateEntityFeature.SPECIFIC_VERSION
            | update.UpdateEntityFeature.BACKUP
            | update.UpdateEntityFeature.INSTALL,
            {"backup": True, "version": "v2.0"},
            True,
            "v2.0",
        ),
        (INSTALL_ACTION, update.UpdateEntityFeature.INSTALL, {}, False, None),
    ],
)
@pytest.mark.usefixtures("setup_update")
async def test_supported_features(
    hass: HomeAssistant,
    supported_feature: update.UpdateEntityFeature,
    action_data: dict,
    calls: list[ServiceCall],
    expected_backup: bool,
    expected_version: str | None,
) -> None:
    """Test release summary and title templates."""
    # Ensure trigger entities trigger.
    state = hass.states.async_set(TEST_INSTALLED_SENSOR, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["supported_features"] == supported_feature

    await hass.services.async_call(
        update.DOMAIN,
        update.SERVICE_INSTALL,
        {"entity_id": TEST_ENTITY_ID, **action_data},
        blocking=True,
    )
    await hass.async_block_till_done()

    # verify
    assert len(calls) == 1
    data = calls[-1].data
    assert data["action"] == "install"
    assert data["caller"] == TEST_ENTITY_ID
    assert data["backup"] == expected_backup
    assert data["specific_version"] == expected_version


@pytest.mark.parametrize(
    ("installed_template", "latest_template", "attribute", "attribute_template"),
    [
        (
            TEST_INSTALLED_TEMPLATE,
            TEST_LATEST_TEMPLATE,
            "availability",
            "{{ 'sensor.test_update' | has_value }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_single_attribute_update")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""
    hass.states.async_set(TEST_SENSOR_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

    hass.states.async_set(TEST_SENSOR_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(TEST_SENSOR_ID, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("installed_template", "latest_template", "attribute", "attribute_template"),
    [
        (
            TEST_INSTALLED_TEMPLATE,
            TEST_LATEST_TEMPLATE,
            "availability",
            "{{ x - 12 }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_single_attribute_update")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    caplog_setup_text,
) -> None:
    """Test that an invalid availability keeps the device available."""
    # Ensure entity triggers
    hass.states.async_set(TEST_SENSOR_ID, "anything")
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state != STATE_UNAVAILABLE

    error = "UndefinedError: 'x' is undefined"
    assert error in caplog_setup_text or error in caplog.text


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "update": {
                    "name": TEST_OBJECT_ID,
                    "installed_version": "{{ trigger.event.data.action }}",
                    "latest_version": "{{ '1.0.2' }}",
                    "picture": "{{ '/local/dogs.png' }}",
                    "icon": "{{ 'mdi:pirate' }}",
                },
            },
        },
    ],
)
async def test_trigger_entity_restore_state(
    hass: HomeAssistant,
    count: int,
    domain: str,
    config: dict,
) -> None:
    """Test restoring trigger entities."""
    restored_attributes = {
        "installed_version": "1.0.0",
        "latest_version": "1.0.1",
        "entity_picture": "/local/cats.png",
        "icon": "mdi:ship",
        "skipped_version": "1.0.1",
    }
    fake_state = State(
        TEST_ENTITY_ID,
        STATE_OFF,
        restored_attributes,
    )
    mock_restore_cache_with_extra_data(hass, ((fake_state, {}),))
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )

        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF
    for attr, value in restored_attributes.items():
        assert state.attributes[attr] == value

    hass.bus.async_fire("test_event", {"action": "1.0.0"})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes["icon"] == "mdi:pirate"
    assert state.attributes["entity_picture"] == "/local/dogs.png"


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("updates", "style"),
    [
        (
            [
                {
                    "name": "test_template_event_01",
                    **TEST_UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_event_02",
                    **TEST_UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.MODERN,
        ),
        (
            [
                {
                    "name": "test_template_event_01",
                    **TEST_UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_event_02",
                    **TEST_UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.TRIGGER,
        ),
    ],
)
async def test_unique_id(
    hass: HomeAssistant, count: int, updates: list[dict], style: ConfigurationStyle
) -> None:
    """Test unique_id option only creates one update entity per id."""
    config = {"update": updates}
    if style == ConfigurationStyle.TRIGGER:
        config = {**config, **TEST_STATE_TRIGGER}
    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {"template": config},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("update")) == 1


async def test_nested_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unique_id option creates one update entity per nested id."""

    with assert_setup_component(1, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {
                "template": {
                    "unique_id": "x",
                    "update": [
                        {
                            "name": "test_a",
                            **TEST_UPDATE_CONFIG,
                            "unique_id": "a",
                        },
                        {
                            "name": "test_b",
                            **TEST_UPDATE_CONFIG,
                            "unique_id": "b",
                        },
                    ],
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("update")) == 2

    entry = entity_registry.async_get("update.test_a")
    assert entry
    assert entry.unique_id == "x-a"

    entry = entity_registry.async_get("update.test_b")
    assert entry
    assert entry.unique_id == "x-b"


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        update.DOMAIN,
        {"name": "My template", **TEST_UPDATE_CONFIG},
    )

    assert state["state"] == STATE_ON
    assert state["attributes"]["installed_version"] == "1.0"
    assert state["attributes"]["latest_version"] == "2.0"
