"""Test service helpers."""
from collections import OrderedDict
from copy import deepcopy
import unittest
from unittest.mock import AsyncMock, Mock, patch

import pytest
import voluptuous as vol

# To prevent circular import when running just this file
from homeassistant import core as ha, exceptions
from homeassistant.auth.permissions import PolicyPermissions
import homeassistant.components  # noqa: F401, pylint: disable=unused-import
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers import (
    device_registry as dev_reg,
    entity_registry as ent_reg,
    service,
    template,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.setup import async_setup_component

from tests.common import (
    MockEntity,
    get_test_home_assistant,
    mock_device_registry,
    mock_registry,
    mock_service,
)

SUPPORT_A = 1
SUPPORT_B = 2
SUPPORT_C = 4


@pytest.fixture
def mock_handle_entity_call():
    """Mock service platform call."""
    with patch(
        "homeassistant.helpers.service._handle_entity_call",
        return_value=None,
    ) as mock_call:
        yield mock_call


@pytest.fixture
def mock_entities(hass):
    """Return mock entities in an ordered dict."""
    kitchen = MockEntity(
        entity_id="light.kitchen",
        available=True,
        should_poll=False,
        supported_features=SUPPORT_A,
    )
    living_room = MockEntity(
        entity_id="light.living_room",
        available=True,
        should_poll=False,
        supported_features=SUPPORT_B,
    )
    bedroom = MockEntity(
        entity_id="light.bedroom",
        available=True,
        should_poll=False,
        supported_features=(SUPPORT_A | SUPPORT_B),
    )
    bathroom = MockEntity(
        entity_id="light.bathroom",
        available=True,
        should_poll=False,
        supported_features=(SUPPORT_B | SUPPORT_C),
    )
    entities = OrderedDict()
    entities[kitchen.entity_id] = kitchen
    entities[living_room.entity_id] = living_room
    entities[bedroom.entity_id] = bedroom
    entities[bathroom.entity_id] = bathroom
    return entities


@pytest.fixture
def area_mock(hass):
    """Mock including area info."""
    hass.states.async_set("light.Bowl", STATE_ON)
    hass.states.async_set("light.Ceiling", STATE_OFF)
    hass.states.async_set("light.Kitchen", STATE_OFF)

    device_in_area = dev_reg.DeviceEntry(area_id="test-area")
    device_no_area = dev_reg.DeviceEntry(id="device-no-area-id")
    device_diff_area = dev_reg.DeviceEntry(area_id="diff-area")

    mock_device_registry(
        hass,
        {
            device_in_area.id: device_in_area,
            device_no_area.id: device_no_area,
            device_diff_area.id: device_diff_area,
        },
    )

    entity_in_own_area = ent_reg.RegistryEntry(
        entity_id="light.in_own_area",
        unique_id="in-own-area-id",
        platform="test",
        area_id="own-area",
    )
    entity_in_area = ent_reg.RegistryEntry(
        entity_id="light.in_area",
        unique_id="in-area-id",
        platform="test",
        device_id=device_in_area.id,
    )
    entity_in_other_area = ent_reg.RegistryEntry(
        entity_id="light.in_other_area",
        unique_id="in-other-area-id",
        platform="test",
        device_id=device_in_area.id,
        area_id="other-area",
    )
    entity_assigned_to_area = ent_reg.RegistryEntry(
        entity_id="light.assigned_to_area",
        unique_id="assigned-area-id",
        platform="test",
        device_id=device_in_area.id,
        area_id="test-area",
    )
    entity_no_area = ent_reg.RegistryEntry(
        entity_id="light.no_area",
        unique_id="no-area-id",
        platform="test",
        device_id=device_no_area.id,
    )
    entity_diff_area = ent_reg.RegistryEntry(
        entity_id="light.diff_area",
        unique_id="diff-area-id",
        platform="test",
        device_id=device_diff_area.id,
    )
    mock_registry(
        hass,
        {
            entity_in_own_area.entity_id: entity_in_own_area,
            entity_in_area.entity_id: entity_in_area,
            entity_in_other_area.entity_id: entity_in_other_area,
            entity_assigned_to_area.entity_id: entity_assigned_to_area,
            entity_no_area.entity_id: entity_no_area,
            entity_diff_area.entity_id: entity_diff_area,
        },
    )


class TestServiceHelpers(unittest.TestCase):
    """Test the Home Assistant service helpers."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.calls = mock_service(self.hass, "test_domain", "test_service")

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_service_call(self):
        """Test service call with templating."""
        config = {
            "service": "{{ 'test_domain.test_service' }}",
            "entity_id": "hello.world",
            "data": {
                "hello": "{{ 'goodbye' }}",
                "effect": {"value": "{{ 'complex' }}", "simple": "simple"},
            },
            "data_template": {"list": ["{{ 'list' }}", "2"]},
            "target": {"area_id": "test-area-id", "entity_id": "will.be_overridden"},
        }

        service.call_from_config(self.hass, config)
        self.hass.block_till_done()

        assert dict(self.calls[0].data) == {
            "hello": "goodbye",
            "effect": {
                "value": "complex",
                "simple": "simple",
            },
            "list": ["list", "2"],
            "entity_id": ["hello.world"],
            "area_id": ["test-area-id"],
        }

    def test_service_template_service_call(self):
        """Test legacy service_template call with templating."""
        config = {
            "service_template": "{{ 'test_domain.test_service' }}",
            "entity_id": "hello.world",
            "data": {"hello": "goodbye"},
        }

        service.call_from_config(self.hass, config)
        self.hass.block_till_done()

        assert self.calls[0].data["hello"] == "goodbye"

    def test_passing_variables_to_templates(self):
        """Test passing variables to templates."""
        config = {
            "service_template": "{{ var_service }}",
            "entity_id": "hello.world",
            "data_template": {"hello": "{{ var_data }}"},
        }

        service.call_from_config(
            self.hass,
            config,
            variables={
                "var_service": "test_domain.test_service",
                "var_data": "goodbye",
            },
        )
        self.hass.block_till_done()

        assert self.calls[0].data["hello"] == "goodbye"

    def test_bad_template(self):
        """Test passing bad template."""
        config = {
            "service_template": "{{ var_service }}",
            "entity_id": "hello.world",
            "data_template": {"hello": "{{ states + unknown_var }}"},
        }

        service.call_from_config(
            self.hass,
            config,
            variables={
                "var_service": "test_domain.test_service",
                "var_data": "goodbye",
            },
        )
        self.hass.block_till_done()

        assert len(self.calls) == 0

    def test_split_entity_string(self):
        """Test splitting of entity string."""
        service.call_from_config(
            self.hass,
            {
                "service": "test_domain.test_service",
                "entity_id": "hello.world, sensor.beer",
            },
        )
        self.hass.block_till_done()
        assert ["hello.world", "sensor.beer"] == self.calls[-1].data.get("entity_id")

    def test_not_mutate_input(self):
        """Test for immutable input."""
        config = cv.SERVICE_SCHEMA(
            {
                "service": "test_domain.test_service",
                "entity_id": "hello.world, sensor.beer",
                "data": {"hello": 1},
                "data_template": {"nested": {"value": "{{ 1 + 1 }}"}},
            }
        )
        orig = deepcopy(config)

        # Only change after call is each template getting hass attached
        template.attach(self.hass, orig)

        service.call_from_config(self.hass, config, validate_config=False)
        assert orig == config

    @patch("homeassistant.helpers.service._LOGGER.error")
    def test_fail_silently_if_no_service(self, mock_log):
        """Test failing if service is missing."""
        service.call_from_config(self.hass, None)
        assert mock_log.call_count == 1

        service.call_from_config(self.hass, {})
        assert mock_log.call_count == 2

        service.call_from_config(self.hass, {"service": "invalid"})
        assert mock_log.call_count == 3


async def test_extract_entity_ids(hass):
    """Test extract_entity_ids method."""
    hass.states.async_set("light.Bowl", STATE_ON)
    hass.states.async_set("light.Ceiling", STATE_OFF)
    hass.states.async_set("light.Kitchen", STATE_OFF)

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await hass.components.group.Group.async_create_group(
        hass, "test", ["light.Ceiling", "light.Kitchen"]
    )

    call = ha.ServiceCall("light", "turn_on", {ATTR_ENTITY_ID: "light.Bowl"})

    assert {"light.bowl"} == await service.async_extract_entity_ids(hass, call)

    call = ha.ServiceCall("light", "turn_on", {ATTR_ENTITY_ID: "group.test"})

    assert {"light.ceiling", "light.kitchen"} == await service.async_extract_entity_ids(
        hass, call
    )

    assert {"group.test"} == await service.async_extract_entity_ids(
        hass, call, expand_group=False
    )

    assert (
        await service.async_extract_entity_ids(
            hass,
            ha.ServiceCall("light", "turn_on", {ATTR_ENTITY_ID: ENTITY_MATCH_NONE}),
        )
        == set()
    )


async def test_extract_entity_ids_from_area(hass, area_mock):
    """Test extract_entity_ids method with areas."""
    call = ha.ServiceCall("light", "turn_on", {"area_id": "own-area"})

    assert {
        "light.in_own_area",
    } == await service.async_extract_entity_ids(hass, call)

    call = ha.ServiceCall("light", "turn_on", {"area_id": "test-area"})

    assert {
        "light.in_area",
        "light.assigned_to_area",
    } == await service.async_extract_entity_ids(hass, call)

    call = ha.ServiceCall("light", "turn_on", {"area_id": ["test-area", "diff-area"]})

    assert {
        "light.in_area",
        "light.diff_area",
        "light.assigned_to_area",
    } == await service.async_extract_entity_ids(hass, call)

    assert (
        await service.async_extract_entity_ids(
            hass, ha.ServiceCall("light", "turn_on", {"area_id": ENTITY_MATCH_NONE})
        )
        == set()
    )


async def test_async_get_all_descriptions(hass):
    """Test async_get_all_descriptions."""
    group = hass.components.group
    group_config = {group.DOMAIN: {}}
    await async_setup_component(hass, group.DOMAIN, group_config)
    descriptions = await service.async_get_all_descriptions(hass)

    assert len(descriptions) == 1

    assert "description" in descriptions["group"]["reload"]
    assert "fields" in descriptions["group"]["reload"]

    logger = hass.components.logger
    logger_config = {logger.DOMAIN: {}}
    await async_setup_component(hass, logger.DOMAIN, logger_config)
    descriptions = await service.async_get_all_descriptions(hass)

    assert len(descriptions) == 2

    assert "description" in descriptions[logger.DOMAIN]["set_level"]
    assert "fields" in descriptions[logger.DOMAIN]["set_level"]


async def test_call_with_required_features(hass, mock_entities):
    """Test service calls invoked only if entity has required features."""
    test_service_mock = AsyncMock(return_value=None)
    await service.entity_service_call(
        hass,
        [Mock(entities=mock_entities)],
        test_service_mock,
        ha.ServiceCall("test_domain", "test_service", {"entity_id": "all"}),
        required_features=[SUPPORT_A],
    )

    assert test_service_mock.call_count == 2
    expected = [
        mock_entities["light.kitchen"],
        mock_entities["light.bedroom"],
    ]
    actual = [call[0][0] for call in test_service_mock.call_args_list]
    assert all(entity in actual for entity in expected)


async def test_call_with_both_required_features(hass, mock_entities):
    """Test service calls invoked only if entity has both features."""
    test_service_mock = AsyncMock(return_value=None)
    await service.entity_service_call(
        hass,
        [Mock(entities=mock_entities)],
        test_service_mock,
        ha.ServiceCall("test_domain", "test_service", {"entity_id": "all"}),
        required_features=[SUPPORT_A | SUPPORT_B],
    )

    assert test_service_mock.call_count == 1
    assert [call[0][0] for call in test_service_mock.call_args_list] == [
        mock_entities["light.bedroom"]
    ]


async def test_call_with_one_of_required_features(hass, mock_entities):
    """Test service calls invoked with one entity having the required features."""
    test_service_mock = AsyncMock(return_value=None)
    await service.entity_service_call(
        hass,
        [Mock(entities=mock_entities)],
        test_service_mock,
        ha.ServiceCall("test_domain", "test_service", {"entity_id": "all"}),
        required_features=[SUPPORT_A, SUPPORT_C],
    )

    assert test_service_mock.call_count == 3
    expected = [
        mock_entities["light.kitchen"],
        mock_entities["light.bedroom"],
        mock_entities["light.bathroom"],
    ]
    actual = [call[0][0] for call in test_service_mock.call_args_list]
    assert all(entity in actual for entity in expected)


async def test_call_with_sync_func(hass, mock_entities):
    """Test invoking sync service calls."""
    test_service_mock = Mock(return_value=None)
    await service.entity_service_call(
        hass,
        [Mock(entities=mock_entities)],
        test_service_mock,
        ha.ServiceCall("test_domain", "test_service", {"entity_id": "light.kitchen"}),
    )
    assert test_service_mock.call_count == 1


async def test_call_with_sync_attr(hass, mock_entities):
    """Test invoking sync service calls."""
    mock_method = mock_entities["light.kitchen"].sync_method = Mock(return_value=None)
    await service.entity_service_call(
        hass,
        [Mock(entities=mock_entities)],
        "sync_method",
        ha.ServiceCall(
            "test_domain",
            "test_service",
            {"entity_id": "light.kitchen", "area_id": "abcd"},
        ),
    )
    assert mock_method.call_count == 1
    # We pass empty kwargs because both entity_id and area_id are filtered out
    assert mock_method.mock_calls[0][2] == {}


async def test_call_context_user_not_exist(hass):
    """Check we don't allow deleted users to do things."""
    with pytest.raises(exceptions.UnknownUser) as err:
        await service.entity_service_call(
            hass,
            [],
            Mock(),
            ha.ServiceCall(
                "test_domain",
                "test_service",
                context=ha.Context(user_id="non-existing"),
            ),
        )

    assert err.value.context.user_id == "non-existing"


async def test_call_context_target_all(hass, mock_handle_entity_call, mock_entities):
    """Check we only target allowed entities if targeting all."""
    with patch(
        "homeassistant.auth.AuthManager.async_get_user",
        return_value=Mock(
            permissions=PolicyPermissions(
                {"entities": {"entity_ids": {"light.kitchen": True}}}, None
            )
        ),
    ):
        await service.entity_service_call(
            hass,
            [Mock(entities=mock_entities)],
            Mock(),
            ha.ServiceCall(
                "test_domain",
                "test_service",
                data={"entity_id": ENTITY_MATCH_ALL},
                context=ha.Context(user_id="mock-id"),
            ),
        )

    assert len(mock_handle_entity_call.mock_calls) == 1
    assert mock_handle_entity_call.mock_calls[0][1][1].entity_id == "light.kitchen"


async def test_call_context_target_specific(
    hass, mock_handle_entity_call, mock_entities
):
    """Check targeting specific entities."""
    with patch(
        "homeassistant.auth.AuthManager.async_get_user",
        return_value=Mock(
            permissions=PolicyPermissions(
                {"entities": {"entity_ids": {"light.kitchen": True}}}, None
            )
        ),
    ):
        await service.entity_service_call(
            hass,
            [Mock(entities=mock_entities)],
            Mock(),
            ha.ServiceCall(
                "test_domain",
                "test_service",
                {"entity_id": "light.kitchen"},
                context=ha.Context(user_id="mock-id"),
            ),
        )

    assert len(mock_handle_entity_call.mock_calls) == 1
    assert mock_handle_entity_call.mock_calls[0][1][1].entity_id == "light.kitchen"


async def test_call_context_target_specific_no_auth(
    hass, mock_handle_entity_call, mock_entities
):
    """Check targeting specific entities without auth."""
    with pytest.raises(exceptions.Unauthorized) as err:
        with patch(
            "homeassistant.auth.AuthManager.async_get_user",
            return_value=Mock(permissions=PolicyPermissions({}, None)),
        ):
            await service.entity_service_call(
                hass,
                [Mock(entities=mock_entities)],
                Mock(),
                ha.ServiceCall(
                    "test_domain",
                    "test_service",
                    {"entity_id": "light.kitchen"},
                    context=ha.Context(user_id="mock-id"),
                ),
            )

    assert err.value.context.user_id == "mock-id"
    assert err.value.entity_id == "light.kitchen"


async def test_call_no_context_target_all(hass, mock_handle_entity_call, mock_entities):
    """Check we target all if no user context given."""
    await service.entity_service_call(
        hass,
        [Mock(entities=mock_entities)],
        Mock(),
        ha.ServiceCall(
            "test_domain", "test_service", data={"entity_id": ENTITY_MATCH_ALL}
        ),
    )

    assert len(mock_handle_entity_call.mock_calls) == 4
    assert [call[1][1] for call in mock_handle_entity_call.mock_calls] == list(
        mock_entities.values()
    )


async def test_call_no_context_target_specific(
    hass, mock_handle_entity_call, mock_entities
):
    """Check we can target specified entities."""
    await service.entity_service_call(
        hass,
        [Mock(entities=mock_entities)],
        Mock(),
        ha.ServiceCall(
            "test_domain",
            "test_service",
            {"entity_id": ["light.kitchen", "light.non-existing"]},
        ),
    )

    assert len(mock_handle_entity_call.mock_calls) == 1
    assert mock_handle_entity_call.mock_calls[0][1][1].entity_id == "light.kitchen"


async def test_call_with_match_all(
    hass, mock_handle_entity_call, mock_entities, caplog
):
    """Check we only target allowed entities if targeting all."""
    await service.entity_service_call(
        hass,
        [Mock(entities=mock_entities)],
        Mock(),
        ha.ServiceCall("test_domain", "test_service", {"entity_id": "all"}),
    )

    assert len(mock_handle_entity_call.mock_calls) == 4
    assert [call[1][1] for call in mock_handle_entity_call.mock_calls] == list(
        mock_entities.values()
    )


async def test_call_with_omit_entity_id(hass, mock_handle_entity_call, mock_entities):
    """Check service call if we do not pass an entity ID."""
    await service.entity_service_call(
        hass,
        [Mock(entities=mock_entities)],
        Mock(),
        ha.ServiceCall("test_domain", "test_service"),
    )

    assert len(mock_handle_entity_call.mock_calls) == 0


async def test_register_admin_service(hass, hass_read_only_user, hass_admin_user):
    """Test the register admin service."""
    calls = []

    async def mock_service(call):
        calls.append(call)

    hass.helpers.service.async_register_admin_service("test", "test", mock_service)
    hass.helpers.service.async_register_admin_service(
        "test",
        "test2",
        mock_service,
        vol.Schema({vol.Required("required"): cv.boolean}),
    )

    with pytest.raises(exceptions.UnknownUser):
        await hass.services.async_call(
            "test",
            "test",
            {},
            blocking=True,
            context=ha.Context(user_id="non-existing"),
        )
    assert len(calls) == 0

    with pytest.raises(exceptions.Unauthorized):
        await hass.services.async_call(
            "test",
            "test",
            {},
            blocking=True,
            context=ha.Context(user_id=hass_read_only_user.id),
        )
    assert len(calls) == 0

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "test",
            "test",
            {"invalid": True},
            blocking=True,
            context=ha.Context(user_id=hass_admin_user.id),
        )
    assert len(calls) == 0

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "test",
            "test2",
            {},
            blocking=True,
            context=ha.Context(user_id=hass_admin_user.id),
        )
    assert len(calls) == 0

    await hass.services.async_call(
        "test",
        "test2",
        {"required": True},
        blocking=True,
        context=ha.Context(user_id=hass_admin_user.id),
    )
    assert len(calls) == 1
    assert calls[0].context.user_id == hass_admin_user.id


async def test_domain_control_not_async(hass, mock_entities):
    """Test domain verification in a service call with an unknown user."""
    calls = []

    def mock_service_log(call):
        """Define a protected service."""
        calls.append(call)

    with pytest.raises(exceptions.HomeAssistantError):
        hass.helpers.service.verify_domain_control("test_domain")(mock_service_log)


async def test_domain_control_unknown(hass, mock_entities):
    """Test domain verification in a service call with an unknown user."""
    calls = []

    async def mock_service_log(call):
        """Define a protected service."""
        calls.append(call)

    with patch(
        "homeassistant.helpers.entity_registry.async_get_registry",
        return_value=Mock(entities=mock_entities),
    ):
        protected_mock_service = hass.helpers.service.verify_domain_control(
            "test_domain"
        )(mock_service_log)

        hass.services.async_register(
            "test_domain", "test_service", protected_mock_service, schema=None
        )

        with pytest.raises(exceptions.UnknownUser):
            await hass.services.async_call(
                "test_domain",
                "test_service",
                {},
                blocking=True,
                context=ha.Context(user_id="fake_user_id"),
            )
        assert len(calls) == 0


async def test_domain_control_unauthorized(hass, hass_read_only_user):
    """Test domain verification in a service call with an unauthorized user."""
    mock_registry(
        hass,
        {
            "light.kitchen": ent_reg.RegistryEntry(
                entity_id="light.kitchen",
                unique_id="kitchen",
                platform="test_domain",
            )
        },
    )

    calls = []

    async def mock_service_log(call):
        """Define a protected service."""
        calls.append(call)

    protected_mock_service = hass.helpers.service.verify_domain_control("test_domain")(
        mock_service_log
    )

    hass.services.async_register(
        "test_domain", "test_service", protected_mock_service, schema=None
    )

    with pytest.raises(exceptions.Unauthorized):
        await hass.services.async_call(
            "test_domain",
            "test_service",
            {},
            blocking=True,
            context=ha.Context(user_id=hass_read_only_user.id),
        )

    assert len(calls) == 0


async def test_domain_control_admin(hass, hass_admin_user):
    """Test domain verification in a service call with an admin user."""
    mock_registry(
        hass,
        {
            "light.kitchen": ent_reg.RegistryEntry(
                entity_id="light.kitchen",
                unique_id="kitchen",
                platform="test_domain",
            )
        },
    )

    calls = []

    async def mock_service_log(call):
        """Define a protected service."""
        calls.append(call)

    protected_mock_service = hass.helpers.service.verify_domain_control("test_domain")(
        mock_service_log
    )

    hass.services.async_register(
        "test_domain", "test_service", protected_mock_service, schema=None
    )

    await hass.services.async_call(
        "test_domain",
        "test_service",
        {},
        blocking=True,
        context=ha.Context(user_id=hass_admin_user.id),
    )

    assert len(calls) == 1


async def test_domain_control_no_user(hass):
    """Test domain verification in a service call with no user."""
    mock_registry(
        hass,
        {
            "light.kitchen": ent_reg.RegistryEntry(
                entity_id="light.kitchen",
                unique_id="kitchen",
                platform="test_domain",
            )
        },
    )

    calls = []

    async def mock_service_log(call):
        """Define a protected service."""
        calls.append(call)

    protected_mock_service = hass.helpers.service.verify_domain_control("test_domain")(
        mock_service_log
    )

    hass.services.async_register(
        "test_domain", "test_service", protected_mock_service, schema=None
    )

    await hass.services.async_call(
        "test_domain",
        "test_service",
        {},
        blocking=True,
        context=ha.Context(user_id=None),
    )

    assert len(calls) == 1


async def test_extract_from_service_available_device(hass):
    """Test the extraction of entity from service and device is available."""
    entities = [
        MockEntity(name="test_1", entity_id="test_domain.test_1"),
        MockEntity(name="test_2", entity_id="test_domain.test_2", available=False),
        MockEntity(name="test_3", entity_id="test_domain.test_3"),
        MockEntity(name="test_4", entity_id="test_domain.test_4", available=False),
    ]

    call_1 = ha.ServiceCall("test", "service", data={"entity_id": ENTITY_MATCH_ALL})

    assert ["test_domain.test_1", "test_domain.test_3"] == [
        ent.entity_id
        for ent in (await service.async_extract_entities(hass, entities, call_1))
    ]

    call_2 = ha.ServiceCall(
        "test",
        "service",
        data={"entity_id": ["test_domain.test_3", "test_domain.test_4"]},
    )

    assert ["test_domain.test_3"] == [
        ent.entity_id
        for ent in (await service.async_extract_entities(hass, entities, call_2))
    ]

    assert (
        await service.async_extract_entities(
            hass,
            entities,
            ha.ServiceCall(
                "test",
                "service",
                data={"entity_id": ENTITY_MATCH_NONE},
            ),
        )
        == []
    )


async def test_extract_from_service_empty_if_no_entity_id(hass):
    """Test the extraction from service without specifying entity."""
    entities = [
        MockEntity(name="test_1", entity_id="test_domain.test_1"),
        MockEntity(name="test_2", entity_id="test_domain.test_2"),
    ]
    call = ha.ServiceCall("test", "service")

    assert [] == [
        ent.entity_id
        for ent in (await service.async_extract_entities(hass, entities, call))
    ]


async def test_extract_from_service_filter_out_non_existing_entities(hass):
    """Test the extraction of non existing entities from service."""
    entities = [
        MockEntity(name="test_1", entity_id="test_domain.test_1"),
        MockEntity(name="test_2", entity_id="test_domain.test_2"),
    ]

    call = ha.ServiceCall(
        "test",
        "service",
        {"entity_id": ["test_domain.test_2", "test_domain.non_exist"]},
    )

    assert ["test_domain.test_2"] == [
        ent.entity_id
        for ent in (await service.async_extract_entities(hass, entities, call))
    ]


async def test_extract_from_service_area_id(hass, area_mock):
    """Test the extraction using area ID as reference."""
    entities = [
        MockEntity(name="in_area", entity_id="light.in_area"),
        MockEntity(name="no_area", entity_id="light.no_area"),
        MockEntity(name="diff_area", entity_id="light.diff_area"),
    ]

    call = ha.ServiceCall("light", "turn_on", {"area_id": "test-area"})
    extracted = await service.async_extract_entities(hass, entities, call)
    assert len(extracted) == 1
    assert extracted[0].entity_id == "light.in_area"

    call = ha.ServiceCall("light", "turn_on", {"area_id": ["test-area", "diff-area"]})
    extracted = await service.async_extract_entities(hass, entities, call)
    assert len(extracted) == 2
    assert sorted(ent.entity_id for ent in extracted) == [
        "light.diff_area",
        "light.in_area",
    ]

    call = ha.ServiceCall(
        "light",
        "turn_on",
        {"area_id": ["test-area", "diff-area"], "device_id": "device-no-area-id"},
    )
    extracted = await service.async_extract_entities(hass, entities, call)
    assert len(extracted) == 3
    assert sorted(ent.entity_id for ent in extracted) == [
        "light.diff_area",
        "light.in_area",
        "light.no_area",
    ]


async def test_entity_service_call_warn_referenced(hass, caplog):
    """Test we only warn for referenced entities in entity_service_call."""
    call = ha.ServiceCall(
        "light",
        "turn_on",
        {
            "area_id": "non-existent-area",
            "entity_id": "non.existent",
            "device_id": "non-existent-device",
        },
    )
    await service.entity_service_call(hass, {}, "", call)
    assert (
        "Unable to find referenced areas non-existent-area, devices non-existent-device, entities non.existent"
        in caplog.text
    )


async def test_async_extract_entities_warn_referenced(hass, caplog):
    """Test we only warn for referenced entities in async_extract_entities."""
    call = ha.ServiceCall(
        "light",
        "turn_on",
        {
            "area_id": "non-existent-area",
            "entity_id": "non.existent",
            "device_id": "non-existent-device",
        },
    )
    extracted = await service.async_extract_entities(hass, {}, call)
    assert len(extracted) == 0
    assert (
        "Unable to find referenced areas non-existent-area, devices non-existent-device, entities non.existent"
        in caplog.text
    )
