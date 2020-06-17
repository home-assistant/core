"""Tests for the Withings component."""
from asynctest import MagicMock, patch
import pytest
import voluptuous as vol
from withings_api.common import UnauthorizedException

from homeassistant.components.withings import CONFIG_SCHEMA, DOMAIN, async_setup, const
from homeassistant.components.withings.common import DataManager
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common import (
    ComponentFactory,
    async_get_flow_for_user_id,
    get_data_manager_by_user_id,
    new_profile_config,
)

from tests.common import MockConfigEntry


def config_schema_validate(withings_config) -> dict:
    """Assert a schema config succeeds."""
    hass_config = {const.DOMAIN: withings_config}

    return CONFIG_SCHEMA(hass_config)


def config_schema_assert_fail(withings_config) -> None:
    """Assert a schema config will fail."""
    try:
        config_schema_validate(withings_config)
        assert False, "This line should not have run."
    except vol.error.MultipleInvalid:
        assert True


def test_config_schema_basic_config() -> None:
    """Test schema."""
    config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_USE_WEBHOOK: True,
            const.CONF_PROFILES: ["Person 1", "Person 2"],
        }
    )


def test_config_schema_client_id() -> None:
    """Test schema."""
    config_schema_assert_fail(
        {
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: ["Person 1", "Person 2"],
        }
    )
    config_schema_assert_fail(
        {
            CONF_CLIENT_SECRET: "my_client_secret",
            CONF_CLIENT_ID: "",
            const.CONF_PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            CONF_CLIENT_SECRET: "my_client_secret",
            CONF_CLIENT_ID: "my_client_id",
            const.CONF_PROFILES: ["Person 1"],
        }
    )


def test_config_schema_client_secret() -> None:
    """Test schema."""
    config_schema_assert_fail(
        {CONF_CLIENT_ID: "my_client_id", const.CONF_PROFILES: ["Person 1"]}
    )
    config_schema_assert_fail(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "",
            const.CONF_PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: ["Person 1"],
        }
    )


def test_config_schema_use_webhook() -> None:
    """Test schema."""
    config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: ["Person 1"],
        }
    )
    config = config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_USE_WEBHOOK: True,
            const.CONF_PROFILES: ["Person 1"],
        }
    )
    assert config[const.DOMAIN][const.CONF_USE_WEBHOOK] is True
    config = config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_USE_WEBHOOK: False,
            const.CONF_PROFILES: ["Person 1"],
        }
    )
    assert config[const.DOMAIN][const.CONF_USE_WEBHOOK] is False
    config_schema_assert_fail(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_USE_WEBHOOK: "A",
            const.CONF_PROFILES: ["Person 1"],
        }
    )


def test_config_schema_profiles() -> None:
    """Test schema."""
    config_schema_assert_fail(
        {CONF_CLIENT_ID: "my_client_id", CONF_CLIENT_SECRET: "my_client_secret"}
    )
    config_schema_assert_fail(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: "",
        }
    )
    config_schema_assert_fail(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: [],
        }
    )
    config_schema_assert_fail(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: ["Person 1", "Person 1"],
        }
    )
    config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: ["Person 1", "Person 2"],
        }
    )


async def test_async_setup_no_config(hass: HomeAssistant) -> None:
    """Test method."""
    hass.async_create_task = MagicMock()

    await async_setup(hass, {})

    hass.async_create_task.assert_not_called()


@pytest.mark.parametrize(
    ["exception"],
    [
        [UnauthorizedException("401")],
        [UnauthorizedException("401")],
        [Exception("401, this is the message")],
    ],
)
async def test_auth_failure(
    hass: HomeAssistant, component_factory: ComponentFactory, exception: Exception
) -> None:
    """Test auth failure."""
    person0 = new_profile_config(
        "person0",
        0,
        api_response_user_get_device=exception,
        api_response_measure_get_meas=exception,
        api_response_sleep_get_summary=exception,
    )

    await component_factory.configure_component(profile_configs=(person0,))
    assert not async_get_flow_for_user_id(hass, person0.user_id)

    await component_factory.setup_profile(person0.user_id)
    data_manager = get_data_manager_by_user_id(hass, person0.user_id)
    await data_manager.poll_data_update_coordinator.async_refresh()

    flows = async_get_flow_for_user_id(hass, person0.user_id)
    assert flows
    assert len(flows) == 1

    flow = flows[0]
    assert flow["handler"] == const.DOMAIN
    assert flow["context"]["profile"] == person0.profile
    assert flow["context"]["userid"] == person0.user_id

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )
    assert result
    assert result["type"] == "external"
    assert result["handler"] == const.DOMAIN
    assert result["step_id"] == "auth"

    await component_factory.unload(person0)


async def test_set_config_unique_id(
    hass: HomeAssistant, component_factory: ComponentFactory
) -> None:
    """Test upgrading configs to use a unique id."""
    person0 = new_profile_config("person0", 0)

    await component_factory.configure_component(profile_configs=(person0,))

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": {"userid": "my_user_id"}, "profile": person0.profile},
    )

    with patch("homeassistant.components.withings.async_get_data_manager") as mock:
        data_manager: DataManager = MagicMock(spec=DataManager)
        data_manager.poll_data_update_coordinator = MagicMock(
            spec=DataUpdateCoordinator
        )
        data_manager.poll_data_update_coordinator.last_update_success = True
        mock.return_value = data_manager
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.unique_id == "my_user_id"
