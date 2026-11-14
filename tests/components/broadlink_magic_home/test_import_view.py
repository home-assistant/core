"""Tests for the Magic Home family import HTTP endpoint."""

import asyncio
import base64
from collections.abc import AsyncIterator
import json
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.broadlink_magic_home.const import DOMAIN, IMPORT_PATH
from homeassistant.components.broadlink_magic_home.import_session import (
    get_import_manager,
)
from homeassistant.components.broadlink_magic_home.import_view import (
    async_register_import_view,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


def _payload(bletoken: str = "00010203") -> bytes:
    family_info = base64.b64encode(
        json.dumps({"name": "Test home", "bletoken": bletoken}).encode()
    ).decode()
    devlist = base64.b64encode(
        json.dumps(
            [
                {
                    "did": "00000000000000000000aabbccddeeff",
                    "pid": "0000000000000000000000008baf0000",
                    "mac": "aabbccddeeff",
                    "devname": "RM Max",
                }
            ]
        ).encode()
    ).decode()
    return json.dumps(
        [
            {
                "did": "family-1",
                "dataList": [
                    {"mtag": "familyInfo", "data": family_info},
                    {"mtag": "devlist", "data": devlist},
                ],
            }
        ]
    ).encode()


async def test_family_import_and_replay_rejection(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test successful one-time App import."""
    assert await async_setup_component(hass, DOMAIN, {})
    async_register_import_view(hass)
    session = get_import_manager(hass).create()
    client = await hass_client()

    response = await client.post(
        f"{IMPORT_PATH}?projectid={session.project_id}&sharetype=saas_carpark",
        data=_payload(),
    )
    assert response.status == 200
    assert (await response.json())["status"] == 0
    assert session.families is not None
    assert session.families[0].family_id == "family-1"

    response = await client.post(
        f"{IMPORT_PATH}?projectid={session.project_id}",
        data=_payload(),
    )
    assert response.status == 200
    assert (await response.json())["status"] == -1


async def test_invalid_session_and_payload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test invalid sessions and malformed payloads."""
    assert await async_setup_component(hass, DOMAIN, {})
    async_register_import_view(hass)
    client = await hass_client()

    response = await client.post(f"{IMPORT_PATH}?projectid=unknown", data=_payload())
    assert (await response.json())["status"] == -1

    session = get_import_manager(hass).create()
    response = await client.post(
        f"{IMPORT_PATH}?projectid={session.project_id}",
        data=b"not json",
    )
    assert (await response.json())["status"] == -1
    assert session.consumed is False


@pytest.mark.parametrize("bletoken", ["", "not-hex"])
async def test_missing_or_invalid_bletoken_is_rejected(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    bletoken: str,
) -> None:
    """Test a family without a usable FastCon token is rejected."""
    assert await async_setup_component(hass, DOMAIN, {})
    async_register_import_view(hass)
    session = get_import_manager(hass).create()
    client = await hass_client()

    response = await client.post(
        f"{IMPORT_PATH}?projectid={session.project_id}",
        data=_payload(bletoken),
    )
    assert (await response.json())["status"] == -1
    assert session.consumed is False


async def test_unexpected_field_types_are_rejected_without_logging_values(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test malformed field types get an error response instead of a 500."""
    assert await async_setup_component(hass, DOMAIN, {})
    async_register_import_view(hass)
    client = await hass_client()
    devlist = base64.b64encode(
        json.dumps(
            [{"did": "gateway", "devname": "Lamp", "shortaddr": ["secret-value"]}]
        ).encode()
    ).decode()
    body = json.dumps(
        [{"did": "family-1", "dataList": [{"mtag": "devlist", "data": devlist}]}]
    ).encode()

    session = get_import_manager(hass).create()
    response = await client.post(
        f"{IMPORT_PATH}?projectid={session.project_id}", data=body
    )
    assert response.status == 200
    assert (await response.json())["status"] == -1
    assert session.consumed is False
    assert "Rejected invalid BroadLink Magic family import" in caplog.text
    assert "secret-value" not in caplog.text


async def test_expired_and_removed_sessions_are_rejected(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test uploads after expiry or flow cancellation are rejected."""
    assert await async_setup_component(hass, DOMAIN, {})
    async_register_import_view(hass)
    manager = get_import_manager(hass)
    client = await hass_client()

    expired = manager.create()
    expired.created_at = 0
    response = await client.post(
        f"{IMPORT_PATH}?projectid={expired.project_id}", data=_payload()
    )
    assert (await response.json())["status"] == -1
    assert expired.families is None
    assert manager.active_sessions == ()

    removed = manager.create("flow-1")
    manager.remove(removed.project_id)
    response = await client.post(
        f"{IMPORT_PATH}?projectid={removed.project_id}", data=_payload()
    )
    assert (await response.json())["status"] == -1
    assert removed.families is None


async def test_concurrent_uploads_complete_once(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test only one of several concurrent uploads is accepted."""
    assert await async_setup_component(hass, DOMAIN, {})
    async_register_import_view(hass)
    session = get_import_manager(hass).create()
    client = await hass_client()

    responses = await asyncio.gather(
        *(
            client.post(
                f"{IMPORT_PATH}?projectid={session.project_id}", data=_payload()
            )
            for _ in range(3)
        )
    )
    statuses = sorted([(await response.json())["status"] for response in responses])
    assert statuses == [-1, -1, 0]


async def test_oversized_upload_is_rejected(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test bodies over the import limit are rejected without consuming the session."""
    assert await async_setup_component(hass, DOMAIN, {})
    async_register_import_view(hass)
    session = get_import_manager(hass).create()
    client = await hass_client()

    async def chunked() -> AsyncIterator[bytes]:
        yield _payload()

    with patch(
        "homeassistant.components.broadlink_magic_home.import_view.MAX_IMPORT_SIZE",
        len(_payload()) - 1,
    ):
        response = await client.post(
            f"{IMPORT_PATH}?projectid={session.project_id}", data=_payload()
        )
        assert (await response.json())["status"] == -1
        response = await client.post(
            f"{IMPORT_PATH}?projectid={session.project_id}", data=chunked()
        )
        assert (await response.json())["status"] == -1
    assert session.consumed is False


async def test_upload_content_type_is_not_required(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the App body is parsed regardless of the declared content type."""
    assert await async_setup_component(hass, DOMAIN, {})
    async_register_import_view(hass)
    session = get_import_manager(hass).create()
    client = await hass_client()

    response = await client.post(
        f"{IMPORT_PATH}?projectid={session.project_id}",
        data=_payload(),
        headers={"Content-Type": "text/plain"},
    )
    assert (await response.json())["status"] == 0


async def test_get_is_not_allowed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the unauthenticated view exposes no read method."""
    assert await async_setup_component(hass, DOMAIN, {})
    async_register_import_view(hass)
    session = get_import_manager(hass).create()
    client = await hass_client()

    response = await client.get(f"{IMPORT_PATH}?projectid={session.project_id}")
    assert response.status == 405


async def test_missing_session(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a missing import session."""
    assert await async_setup_component(hass, DOMAIN, {})
    async_register_import_view(hass)
    client = await hass_client()

    response = await client.post(IMPORT_PATH, data=_payload())
    assert (await response.json())["status"] == -1


async def test_session_consumed_during_import(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the final single-consumer guard."""
    assert await async_setup_component(hass, DOMAIN, {})
    async_register_import_view(hass)
    session = get_import_manager(hass).create()
    client = await hass_client()

    with patch(
        "homeassistant.components.broadlink_magic_home.import_session.ImportSession.complete",
        return_value=False,
    ):
        response = await client.post(
            f"{IMPORT_PATH}?projectid={session.project_id}",
            data=_payload(),
        )
    assert (await response.json())["status"] == -1


async def test_successful_upload_advances_config_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test App upload automatically advances its config flow."""
    assert await async_setup_component(hass, DOMAIN, {})
    async_register_import_view(hass)
    session = get_import_manager(hass).create("flow-1")
    client = await hass_client()

    with patch.object(
        hass.config_entries.flow,
        "async_configure",
        new_callable=AsyncMock,
    ) as configure:
        response = await client.post(
            f"{IMPORT_PATH}?projectid={session.project_id}",
            data=_payload(),
        )
        assert (await response.json())["status"] == 0
        await hass.async_block_till_done()
    configure.assert_awaited_once_with("flow-1", {})
