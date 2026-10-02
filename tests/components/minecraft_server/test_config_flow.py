"""Tests for the Minecraft Server config flow."""

from unittest.mock import patch

from mcstatus import BedrockServer, JavaServer, LegacyServer
import pytest

from homeassistant.components.minecraft_server.api import MinecraftServerType
from homeassistant.components.minecraft_server.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    TEST_ADDRESS,
    TEST_BEDROCK_STATUS_RESPONSE,
    TEST_HOST,
    TEST_JAVA_STATUS_RESPONSE,
    TEST_LEGACY_JAVA_STATUS_RESPONSE,
    TEST_PORT,
)

from tests.common import MockConfigEntry

SERVER_EDITION_CASE_PARAM_NAMES = (
    "server_type",
    "lookup_target",
    "lookup_result",
    "status_target",
    "status_response",
)

SERVER_EDITION_SUCCESS_CASES = [
    (
        MinecraftServerType.LEGACY_JAVA_EDITION,
        "homeassistant.components.minecraft_server.api.LegacyServer.async_lookup",
        lambda: LegacyServer(host=TEST_HOST, port=TEST_PORT),
        "homeassistant.components.minecraft_server.api.LegacyServer.async_status",
        TEST_LEGACY_JAVA_STATUS_RESPONSE,
    ),
    (
        MinecraftServerType.JAVA_EDITION,
        "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
        lambda: JavaServer(host=TEST_HOST, port=TEST_PORT),
        "homeassistant.components.minecraft_server.api.JavaServer.async_status",
        TEST_JAVA_STATUS_RESPONSE,
    ),
    (
        MinecraftServerType.BEDROCK_EDITION,
        "homeassistant.components.minecraft_server.api.BedrockServer.lookup",
        lambda: BedrockServer(host=TEST_HOST, port=TEST_PORT),
        "homeassistant.components.minecraft_server.api.BedrockServer.async_status",
        TEST_BEDROCK_STATUS_RESPONSE,
    ),
]

SERVER_EDITION_CASE_IDS = ["legacy_java", "java", "bedrock"]


@pytest.mark.parametrize(
    SERVER_EDITION_CASE_PARAM_NAMES,
    SERVER_EDITION_SUCCESS_CASES,
    ids=SERVER_EDITION_CASE_IDS,
)
async def test_full_flow(
    hass: HomeAssistant,
    server_type: MinecraftServerType,
    lookup_target: str,
    lookup_result: callable,
    status_target: str,
    status_response: dict,
) -> None:
    """Test config entry creation for all supported server editions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(lookup_target, return_value=lookup_result()),
        patch(status_target, return_value=status_response),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_ADDRESS
    assert result["data"][CONF_ADDRESS] == TEST_ADDRESS
    assert result["data"][CONF_TYPE] == server_type


@pytest.mark.parametrize(
    SERVER_EDITION_CASE_PARAM_NAMES,
    SERVER_EDITION_SUCCESS_CASES,
    ids=SERVER_EDITION_CASE_IDS,
)
async def test_service_already_configured(
    hass: HomeAssistant,
    server_type: MinecraftServerType,
    lookup_target: str,
    lookup_result: callable,
    status_target: str,
    status_response: dict,
) -> None:
    """Test config flow abort if a server is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_TYPE: server_type},
    )
    entry.add_to_hass(hass)

    with (
        patch(lookup_target, return_value=lookup_result()),
        patch(status_target, return_value=status_response),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    SERVER_EDITION_CASE_PARAM_NAMES,
    SERVER_EDITION_SUCCESS_CASES,
    ids=SERVER_EDITION_CASE_IDS,
)
async def test_recovery(
    hass: HomeAssistant,
    server_type: MinecraftServerType,
    lookup_target: str,
    lookup_result: callable,
    status_target: str,
    status_response: dict,
) -> None:
    """Test recovery flow across all supported server editions."""
    with (
        patch(lookup_target, return_value=lookup_result()),
        patch(status_target, side_effect=OSError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(lookup_target, return_value=lookup_result()),
        patch(status_target, return_value=status_response),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_ADDRESS
    assert result2["data"][CONF_ADDRESS] == TEST_ADDRESS
    assert result2["data"][CONF_TYPE] == server_type


@pytest.mark.parametrize(
    ("server_type", "lookup_target"),
    [
        (
            MinecraftServerType.LEGACY_JAVA_EDITION,
            "homeassistant.components.minecraft_server.api.LegacyServer.async_lookup",
        ),
        (
            MinecraftServerType.JAVA_EDITION,
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
        ),
        (
            MinecraftServerType.BEDROCK_EDITION,
            "homeassistant.components.minecraft_server.api.BedrockServer.lookup",
        ),
    ],
    ids=SERVER_EDITION_CASE_IDS,
)
async def test_address_lookup_error(
    hass: HomeAssistant,
    server_type: MinecraftServerType,
    lookup_target: str,
) -> None:
    """Test config flow handles a server address lookup error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(lookup_target, side_effect=ValueError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_recovery_java(hass: HomeAssistant) -> None:
    """Test config flow recovery with a Java Edition server."""
    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            side_effect=OSError,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: MinecraftServerType.JAVA_EDITION,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=TEST_JAVA_STATUS_RESPONSE,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"],
            user_input={
                CONF_TYPE: MinecraftServerType.JAVA_EDITION,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == TEST_ADDRESS
        assert result2["data"][CONF_ADDRESS] == TEST_ADDRESS
        assert result2["data"][CONF_TYPE] == MinecraftServerType.JAVA_EDITION


async def test_recovery_bedrock(hass: HomeAssistant) -> None:
    """Test config flow recovery with a Bedrock Edition server."""
    with (
        patch(
            "homeassistant.components.minecraft_server.api.BedrockServer.lookup",
            return_value=BedrockServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.BedrockServer.async_status",
            side_effect=OSError,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: MinecraftServerType.BEDROCK_EDITION,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.minecraft_server.api.BedrockServer.lookup",
            return_value=BedrockServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.BedrockServer.async_status",
            return_value=TEST_BEDROCK_STATUS_RESPONSE,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"],
            user_input={
                CONF_TYPE: MinecraftServerType.BEDROCK_EDITION,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == TEST_ADDRESS
        assert result2["data"][CONF_ADDRESS] == TEST_ADDRESS
        assert result2["data"][CONF_TYPE] == MinecraftServerType.BEDROCK_EDITION


async def test_recovery_legacy_java(hass: HomeAssistant) -> None:
    """Test config flow recovery with a legacy Java Edition server."""
    with (
        patch(
            "homeassistant.components.minecraft_server.api.LegacyServer.async_lookup",
            return_value=LegacyServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.LegacyServer.async_status",
            side_effect=OSError,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: MinecraftServerType.LEGACY_JAVA_EDITION,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.minecraft_server.api.LegacyServer.async_lookup",
            return_value=LegacyServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.LegacyServer.async_status",
            return_value=TEST_LEGACY_JAVA_STATUS_RESPONSE,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"],
            user_input={
                CONF_TYPE: MinecraftServerType.LEGACY_JAVA_EDITION,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == TEST_ADDRESS
        assert result2["data"][CONF_ADDRESS] == TEST_ADDRESS
        assert result2["data"][CONF_TYPE] == MinecraftServerType.LEGACY_JAVA_EDITION
