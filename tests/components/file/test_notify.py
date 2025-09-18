"""The tests for the notify file platform."""

import os
from typing import Any
from unittest.mock import MagicMock, call, mock_open, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import notify
from homeassistant.components.file import DOMAIN
from homeassistant.components.notify import ATTR_TITLE_DEFAULT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("domain", "service", "params"),
    [
        (
            notify.DOMAIN,
            "send_message",
            {"entity_id": "notify.test", "message": "one, two, testing, testing"},
        ),
    ],
)
@pytest.mark.parametrize("timestamp", [False, True], ids=["no_timestamp", "timestamp"])
async def test_notify_file(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_is_allowed_path: MagicMock,
    timestamp: bool,
    domain: str,
    service: str,
    params: dict[str, str],
) -> None:
    """Test the notify file output."""
    filename = "mock_file"
    full_filename = os.path.join(hass.config.path(), filename)

    message = params["message"]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"name": "test", "platform": "notify", "file_path": full_filename},
        options={"timestamp": timestamp},
        version=2,
        title=f"test [{filename}]",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    freezer.move_to(dt_util.utcnow())

    m_open = mock_open()
    with (
        patch("homeassistant.components.file.notify.open", m_open, create=True),
        patch("homeassistant.components.file.notify.os.stat") as mock_st,
    ):
        mock_st.return_value.st_size = 0
        title = (
            f"{ATTR_TITLE_DEFAULT} notifications "
            f"(Log started: {dt_util.utcnow().isoformat()})\n{'-' * 80}\n"
        )

        await hass.services.async_call(domain, service, params, blocking=True)

        assert m_open.call_count == 1
        assert m_open.call_args == call(full_filename, "a", encoding="utf8")

        assert m_open.return_value.write.call_count == 2
        if not timestamp:
            assert m_open.return_value.write.call_args_list == [
                call(title),
                call(f"{message}\n"),
            ]
        else:
            assert m_open.return_value.write.call_args_list == [
                call(title),
                call(f"{dt_util.utcnow().isoformat()} {message}\n"),
            ]


@pytest.mark.parametrize(
    ("is_allowed", "config", "options"),
    [
        (
            False,
            {
                "name": "test",
                "platform": "notify",
                "file_path": "mock_file",
            },
            {
                "timestamp": False,
            },
        ),
    ],
    ids=["not_allowed"],
)
async def test_notify_file_not_allowed(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_is_allowed_path: MagicMock,
    config: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """Test notify file output not allowed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        version=2,
        options=options,
        title=f"test [{config['file_path']}]",
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert "is not allowed" in caplog.text


@pytest.mark.parametrize(
    ("service", "params"),
    [
        (
            "send_message",
            {"entity_id": "notify.test", "message": "one, two, testing, testing"},
        )
    ],
)
@pytest.mark.parametrize(
    ("data", "options", "is_allowed"),
    [
        (
            {
                "name": "test",
                "platform": "notify",
                "file_path": "mock_file",
            },
            {
                "timestamp": False,
            },
            True,
        ),
    ],
    ids=["not_allowed"],
)
async def test_notify_file_write_access_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_is_allowed_path: MagicMock,
    service: str,
    params: dict[str, Any],
    data: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """Test the notify file fails."""
    domain = notify.DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        version=2,
        options=options,
        title=f"test [{data['file_path']}]",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)

    freezer.move_to(dt_util.utcnow())

    m_open = mock_open()
    with (
        patch("homeassistant.components.file.notify.open", m_open, create=True),
        patch("homeassistant.components.file.notify.os.stat") as mock_st,
    ):
        mock_st.side_effect = OSError("Access Failed")
        with pytest.raises(ServiceValidationError) as exc:
            await hass.services.async_call(domain, service, params, blocking=True)
        assert f"{exc.value!r}" == "ServiceValidationError('write_access_failed')"
