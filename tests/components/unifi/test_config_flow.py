"""Test UniFi Network config flow."""

from collections.abc import Callable
import socket
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.unifi import async_migrate_entry
from homeassistant.components.unifi.config_entry_unique_id import (
    controller_key_from_system_info,
    extract_site_id,
)
from homeassistant.components.unifi.config_flow import (
    _async_discover_unifi,
    _entry_matches_target,
)
from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
    CONF_CLIENT_SOURCE,
    CONF_DETECTION_TIME,
    CONF_DPI_RESTRICTIONS,
    CONF_IGNORE_WIRED_BUG,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    DOMAIN,
)
from homeassistant.components.unifi.errors import AuthenticationRequired, CannotConnect
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac

from .conftest import ConfigEntryFactoryType

from tests.common import MockConfigEntry

CONTROLLER_MAC = "10:00:00:00:00:01"

CLIENTS = [{"mac": "00:00:00:00:00:01"}]

DEVICES = [
    {
        "board_rev": 21,
        "device_id": "mock-id",
        "ip": "10.0.1.1",
        "last_seen": 0,
        "mac": "00:00:00:00:01:01",
        "model": "U7PG2",
        "name": "access_point",
        "state": 1,
        "type": "uap",
        "version": "4.0.80.10875",
        "wlan_overrides": [
            {
                "name": "SSID 3",
                "radio": "na",
                "radio_name": "wifi1",
                "wlan_id": "012345678910111213141516",
            },
            {
                "name": "",
                "radio": "na",
                "radio_name": "wifi1",
                "wlan_id": "012345678910111213141516",
            },
            {
                "radio": "na",
                "radio_name": "wifi1",
                "wlan_id": "012345678910111213141516",
            },
        ],
    }
]

WLANS = [
    {"_id": "1", "name": "SSID 1", "enabled": True},
    {
        "_id": "2",
        "name": "SSID 2",
        "name_combine_enabled": False,
        "name_combine_suffix": "_IOT",
        "enabled": True,
    },
    {"_id": "3", "name": "SSID 4", "name_combine_enabled": False, "enabled": True},
]

DPI_GROUPS = [
    {
        "_id": "5ba29dd8e3c58f026e9d7c4a",
        "name": "Default",
        "site_id": "5ba29dd4e3c58f026e9d7c38",
    },
]


def test_config_entry_unique_id_helpers() -> None:
    """Test fallback controller keys and empty site IDs."""
    assert (
        controller_key_from_system_info(
            SimpleNamespace(
                raw={},
                anonymous_controller_id=" 24F81231-A456-4C32-ABCD-F5612345385F ",
            )
        )
        == "24f81231-a456-4c32-abcd-f5612345385f"
    )
    assert controller_key_from_system_info(SimpleNamespace(raw={})) is None
    assert extract_site_id(None) is None


def test_entry_matches_target_rejects_different_site_id() -> None:
    """Test entries for different sites are not considered matches."""
    assert not _entry_matches_target(
        entry_unique_id="10:00:00:00:00:01::site-a",
        entry_host="1.2.3.4",
        entry_site_name="site-a",
        target_controller_key="10:00:00:00:00:01",
        target_host="1.2.3.4",
        target_site_id="site-b",
        target_site_name="site-b",
    )


async def test_migrate_entry_rejects_future_version(hass: HomeAssistant) -> None:
    """Future config entry versions should not migrate."""
    existing_entry = MockConfigEntry(domain=DOMAIN, version=3)
    existing_entry.add_to_hass(hass)

    assert not await async_migrate_entry(hass, existing_entry)


async def test_migrate_entry_rejects_entry_without_unique_id(
    hass: HomeAssistant,
) -> None:
    """Migration needs an existing site unique ID to preserve site identity."""
    existing_entry = MockConfigEntry(domain=DOMAIN, unique_id=None, version=1)
    existing_entry.add_to_hass(hass)

    assert not await async_migrate_entry(hass, existing_entry)


async def test_migrate_entry_rejects_connection_error(
    hass: HomeAssistant,
) -> None:
    """Migration should fail if the controller cannot be queried."""
    existing_entry = MockConfigEntry(domain=DOMAIN, unique_id="default", version=1)
    existing_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.unifi.get_unifi_api", side_effect=CannotConnect
    ):
        assert not await async_migrate_entry(hass, existing_entry)


@pytest.mark.parametrize(
    "system_information_payload",
    [[{}]],
)
async def test_migrate_entry_rejects_missing_controller_key(
    hass: HomeAssistant,
    mock_default_requests: None,
) -> None:
    """Migration needs a stable controller key to build the new unique ID."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="default",
        version=1,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_SITE_ID: "default",
            CONF_VERIFY_SSL: False,
        },
    )
    existing_entry.add_to_hass(hass)

    assert not await async_migrate_entry(hass, existing_entry)


@pytest.mark.parametrize(
    "system_information_payload",
    [[{}]],
)
@pytest.mark.usefixtures("mock_default_requests")
async def test_flow_shows_error_without_stable_controller_key(
    hass: HomeAssistant,
) -> None:
    """Config flow should not fall back to host when controller key is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "service_unavailable"}


@pytest.mark.usefixtures("mock_default_requests")
async def test_flow_works(hass: HomeAssistant, mock_discovery) -> None:
    """Test config flow."""
    mock_discovery.return_value = "1"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"]({CONF_USERNAME: "", CONF_PASSWORD: ""}) == {
        CONF_HOST: "unifi",
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_PORT: 443,
        CONF_VERIFY_SSL: False,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4 (Site name)"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
        CONF_PORT: 1234,
        CONF_SITE_ID: "site_id",
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].unique_id == f"{CONTROLLER_MAC}::1"


async def test_flow_works_negative_discovery(hass: HomeAssistant) -> None:
    """Test config flow with a negative outcome of async_discovery_unifi."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"]({CONF_USERNAME: "", CONF_PASSWORD: ""}) == {
        CONF_HOST: "",
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_PORT: 443,
        CONF_VERIFY_SSL: False,
    }


@pytest.mark.parametrize(
    "site_payload",
    [
        [
            {"name": "default", "role": "admin", "desc": "site name", "_id": "1"},
            {"name": "site2", "role": "admin", "desc": "site2 name", "_id": "2"},
        ]
    ],
)
@pytest.mark.usefixtures("mock_default_requests")
async def test_flow_multiple_sites(hass: HomeAssistant) -> None:
    """Test config flow works when finding multiple sites."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "site"
    assert result["data_schema"]({"site": "1"})
    assert result["data_schema"]({"site": "2"})


@pytest.mark.usefixtures("config_entry_setup")
async def test_flow_raise_already_configured(hass: HomeAssistant) -> None:
    """Test config flow aborts since a connected config entry already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("config_entry_setup")
async def test_flow_aborts_configuration_updated(hass: HomeAssistant) -> None:
    """Test config flow aborts since a connected config entry already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("homeassistant.components.unifi.async_setup_entry") and patch(
        "homeassistant.components.unifi.UnifiHub.available", new_callable=PropertyMock
    ) as ws_mock:
        ws_mock.return_value = False
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
                CONF_PORT: 12345,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "configuration_updated"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (AuthenticationRequired, "faulty_credentials"),
        (CannotConnect, "service_unavailable"),
    ],
)
@pytest.mark.usefixtures("mock_default_requests")
async def test_flow_fails_and_recovers(
    hass: HomeAssistant,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test config flow recovers from errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.unifi.config_flow.get_unifi_api",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4 (Site name)"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
        CONF_PORT: 1234,
        CONF_SITE_ID: "site_id",
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].unique_id == f"{CONTROLLER_MAC}::1"


@pytest.mark.parametrize(
    "site_payload",
    [[{"name": "default", "role": "admin", "desc": "Default", "_id": "default"}]],
)
@pytest.mark.parametrize(
    "system_information_payload",
    [[{"anonymous_controller_id": "controller-b", "mac": "10:00:00:00:00:02"}]],
)
async def test_flow_allows_second_controller_with_same_default_site(
    hass: HomeAssistant,
    mock_requests: Callable[[str, str], None],
) -> None:
    """A second controller with the same default site should create a new entry."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="10:00:00:00:00:01::default",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 443,
            CONF_SITE_ID: "default",
            CONF_VERIFY_SSL: False,
        },
    )
    existing_entry.add_to_hass(hass)
    MockConfigEntry(domain="other").add_to_hass(hass)
    mock_requests("10.0.1.1", "default")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "10.0.1.1",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.0.1.1 (Default)"
    assert result["result"].unique_id == "10:00:00:00:00:02::default"


@pytest.mark.parametrize(
    "site_payload",
    [[{"name": "default", "role": "admin", "desc": "Default", "_id": "default"}]],
)
@pytest.mark.parametrize(
    "system_information_payload",
    [[{"anonymous_controller_id": "controller-b", "mac": "10:00:00:00:00:02"}]],
)
async def test_flow_updates_legacy_site_only_entry_data(
    hass: HomeAssistant,
    mock_requests: Callable[[str, str], None],
) -> None:
    """Legacy site-only entries should still be matched by config flow."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="default",
        data={
            CONF_HOST: "10.0.1.1",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 443,
            CONF_SITE_ID: "default",
            CONF_VERIFY_SSL: False,
        },
    )
    existing_entry.add_to_hass(hass)
    mock_requests("10.0.1.1", "default")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "10.0.1.1",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "configuration_updated"
    assert existing_entry.unique_id == "default"


@pytest.mark.parametrize(
    "site_payload",
    [[{"name": "default", "role": "admin", "desc": "Default", "_id": "default"}]],
)
@pytest.mark.parametrize(
    "system_information_payload",
    [[{"anonymous_controller_id": "controller-b", "mac": "10:00:00:00:00:02"}]],
)
async def test_migrate_entry_updates_legacy_site_only_unique_id(
    hass: HomeAssistant,
    mock_default_requests: None,
) -> None:
    """Legacy site-only entries should migrate before setup loads the integration."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="default",
        version=1,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_SITE_ID: "default",
            CONF_VERIFY_SSL: False,
        },
    )
    existing_entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, existing_entry)
    assert existing_entry.version == 2
    assert existing_entry.unique_id == "10:00:00:00:00:02::default"


async def test_reauth_flow_update_configuration(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Verify reauth flow can update hub configuration."""
    config_entry = config_entry_setup

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.unifi.UnifiHub.available", new_callable=PropertyMock
    ) as ws_mock:
        ws_mock.return_value = False
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "new_name",
                CONF_PASSWORD: "new_pass",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_HOST] == "1.2.3.4"
    assert config_entry.data[CONF_USERNAME] == "new_name"
    assert config_entry.data[CONF_PASSWORD] == "new_pass"


@pytest.mark.parametrize(
    "site_payload",
    [[{"name": "default", "role": "admin", "desc": "Default", "_id": "default"}]],
)
@pytest.mark.parametrize(
    "system_information_payload",
    [[{"anonymous_controller_id": "controller-b", "mac": "10:00:00:00:00:02"}]],
)
async def test_reauth_flow_extracts_site_id_from_compound_unique_id(
    hass: HomeAssistant,
    mock_requests: Callable[[str, str], None],
) -> None:
    """Reauth should use the raw site_id from the compound unique ID."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="10:00:00:00:00:02::default",
        data={
            CONF_HOST: "10.0.1.1",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 443,
            CONF_SITE_ID: "default",
            CONF_VERIFY_SSL: False,
        },
    )
    config_entry.add_to_hass(hass)
    mock_requests("10.0.1.1", "default")

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.unifi.UnifiHub.available", new_callable=PropertyMock
    ) as ws_mock:
        ws_mock.return_value = False
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "10.0.1.1",
                CONF_USERNAME: "new_name",
                CONF_PASSWORD: "new_pass",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.unique_id == "10:00:00:00:00:02::default"


async def test_reauth_flow_update_configuration_on_not_loaded_entry(
    hass: HomeAssistant, config_entry_factory: ConfigEntryFactoryType
) -> None:
    """Verify reauth flow can update hub configuration on a not loaded entry."""
    with patch(
        "homeassistant.components.unifi.get_unifi_api",
        side_effect=CannotConnect,
    ):
        config_entry = await config_entry_factory()

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "new_name",
            CONF_PASSWORD: "new_pass",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_HOST] == "1.2.3.4"
    assert config_entry.data[CONF_USERNAME] == "new_name"
    assert config_entry.data[CONF_PASSWORD] == "new_pass"


@pytest.mark.parametrize("client_payload", [CLIENTS])
@pytest.mark.parametrize("device_payload", [DEVICES])
@pytest.mark.parametrize("wlan_payload", [WLANS])
@pytest.mark.parametrize("dpi_group_payload", [DPI_GROUPS])
async def test_advanced_option_flow(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test advanced config flow options."""
    config_entry = config_entry_setup

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_entity_sources"
    assert not result["last_step"]
    assert list(result["data_schema"].schema[CONF_CLIENT_SOURCE].options.keys()) == [
        "00:00:00:00:00:01"
    ]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_CLIENT_SOURCE: ["00:00:00:00:00:01"]},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_tracker"
    assert not result["last_step"]
    assert list(result["data_schema"].schema[CONF_SSID_FILTER].options.keys()) == [
        "",
        "SSID 1",
        "SSID 2",
        "SSID 2_IOT",
        "SSID 3",
        "SSID 4",
    ]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_WIRED_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
            CONF_SSID_FILTER: ["SSID 1", "SSID 2_IOT", "SSID 3", "SSID 4"],
            CONF_DETECTION_TIME: 100,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "client_control"
    assert not result["last_step"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
            CONF_DPI_RESTRICTIONS: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "statistics_sensors"
    assert result["last_step"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_CLIENT_SOURCE: ["00:00:00:00:00:01"],
        CONF_TRACK_CLIENTS: False,
        CONF_TRACK_WIRED_CLIENTS: False,
        CONF_TRACK_DEVICES: False,
        CONF_SSID_FILTER: ["SSID 1", "SSID 2_IOT", "SSID 3", "SSID 4"],
        CONF_DETECTION_TIME: 100,
        CONF_IGNORE_WIRED_BUG: False,
        CONF_DPI_RESTRICTIONS: False,
        CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
        CONF_ALLOW_BANDWIDTH_SENSORS: True,
        CONF_ALLOW_UPTIME_SENSORS: True,
    }


@pytest.mark.parametrize("client_payload", [CLIENTS])
async def test_simple_option_flow(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test simple config flow options."""
    config_entry = config_entry_setup

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "simple_options"
    assert result["last_step"]

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as mock_reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_TRACK_CLIENTS: False,
                CONF_TRACK_DEVICES: False,
                CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
            },
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TRACK_CLIENTS: False,
        CONF_TRACK_DEVICES: False,
        CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
    }
    # Check there is no reload on updating these options
    assert mock_reload.call_count == 0


async def test_discover_unifi_positive(hass: HomeAssistant) -> None:
    """Verify positive run of UniFi discovery."""
    with patch("socket.gethostbyname", return_value="192.168.1.1"):
        assert await _async_discover_unifi(hass) == "192.168.1.1"


async def test_discover_unifi_negative(hass: HomeAssistant) -> None:
    """Verify negative run of UniFi discovery."""
    with patch("socket.gethostbyname", side_effect=socket.gaierror):
        assert await _async_discover_unifi(hass) is None


INTEGRATION_DISCOVERY_INFO = {
    "source_ip": "10.0.0.1",
    "hw_addr": "e0:63:da:20:14:a9",
    "hostname": "UniFi-Dream-Machine",
    "platform": "UCG-Ultra",
    "direct_connect_domain": "x.ui.direct",
}


async def test_flow_integration_discovery(hass: HomeAssistant) -> None:
    """Test we get the form with integration discovery source."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data=INTEGRATION_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert context["title_placeholders"] == {
        "host": "x.ui.direct",
        "site": "default",
    }
    assert context["configuration_url"] == "https://x.ui.direct"


@pytest.mark.usefixtures("config_entry")
async def test_flow_integration_discovery_aborts_if_host_already_exists(
    hass: HomeAssistant,
) -> None:
    """Test we abort if the host is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            **INTEGRATION_DISCOVERY_INFO,
            "source_ip": "1.2.3.4",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_integration_discovery_uses_direct_connect_domain(
    hass: HomeAssistant,
) -> None:
    """Test discovery prefers direct_connect_domain over source_ip."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data=INTEGRATION_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert context["title_placeholders"] == {
        "host": "x.ui.direct",
        "site": "default",
    }

    schema_defaults = {
        marker.schema: marker.default()
        for marker in result["data_schema"].schema
        if hasattr(marker, "default") and callable(marker.default)
    }
    assert schema_defaults[CONF_HOST] == "x.ui.direct"
    assert schema_defaults[CONF_VERIFY_SSL] is True


@pytest.mark.usefixtures("config_entry")
async def test_flow_integration_discovery_aborts_on_direct_connect_host(
    hass: HomeAssistant,
) -> None:
    """Test we abort if the direct connect domain matches a configured host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            **INTEGRATION_DISCOVERY_INFO,
            "source_ip": "10.0.0.1",
            "direct_connect_domain": "1.2.3.4",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_integration_discovery_updates_existing_entry_on_rediscovery(
    hass: HomeAssistant,
) -> None:
    """Test that an existing entry's host is refreshed when rediscovered with the same MAC."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(INTEGRATION_DISCOVERY_INFO["hw_addr"]),
        data={
            CONF_HOST: "old.host",
            CONF_VERIFY_SSL: False,
        },
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data=INTEGRATION_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert old_entry.data[CONF_HOST] == "x.ui.direct"
    assert old_entry.data[CONF_VERIFY_SSL] is True


async def test_flow_integration_discovery_aborts_without_source_ip(
    hass: HomeAssistant,
) -> None:
    """Test we abort discovery when source_ip is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            **INTEGRATION_DISCOVERY_INFO,
            "source_ip": None,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_flow_integration_discovery_gets_form_with_ignored_entry(
    hass: HomeAssistant,
) -> None:
    """Test we can still set up if there is an ignored never configured entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"not_controller_key": None},
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data=INTEGRATION_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert context["title_placeholders"] == {
        "host": "x.ui.direct",
        "site": "default",
    }
