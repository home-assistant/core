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
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, assert_setup_component


async def test_bad_config(hass: HomeAssistant) -> None:
    """Test set up the platform with bad/missing config."""
    config = {notify.DOMAIN: {"name": "test", "platform": "file"}}
    with assert_setup_component(0) as handle_config:
        assert await async_setup_component(hass, notify.DOMAIN, config)
        await hass.async_block_till_done()
    assert not handle_config[notify.DOMAIN]


@pytest.mark.parametrize(
    ("domain", "service", "params"),
    [
        (notify.DOMAIN, "test", {"message": "one, two, testing, testing"}),
        (
            notify.DOMAIN,
            "send_message",
            {"entity_id": "notify.test", "message": "one, two, testing, testing"},
        ),
    ],
    ids=["legacy", "entity"],
)
@pytest.mark.parametrize(
    ("timestamp", "config"),
    [
        (
            False,
            {
                "notify": [
                    {
                        "name": "test",
                        "platform": "file",
                        "filename": "mock_file",
                        "timestamp": False,
                    }
                ]
            },
        ),
        (
            True,
            {
                "notify": [
                    {
                        "name": "test",
                        "platform": "file",
                        "filename": "mock_file",
                        "timestamp": True,
                    }
                ]
            },
        ),
    ],
    ids=["no_timestamp", "timestamp"],
)
async def test_notify_file(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    timestamp: bool,
    mock_is_allowed_path: MagicMock,
    config: ConfigType,
    domain: str,
    service: str,
    params: dict[str, str],
) -> None:
    """Test the notify file output."""
    filename = "mock_file"
    message = params["message"]
    assert await async_setup_component(hass, notify.DOMAIN, config)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)

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

        full_filename = os.path.join(hass.config.path(), filename)
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
    ("domain", "service", "params"),
    [(notify.DOMAIN, "test", {"message": "one, two, testing, testing"})],
    ids=["legacy"],
)
@pytest.mark.parametrize(
    ("is_allowed", "config"),
    [
        (
            False,
            {
                "notify": [
                    {
                        "name": "test",
                        "platform": "file",
                        "filename": "mock_file",
                    }
                ]
            },
        ),
    ],
    ids=["not_allowed"],
)
async def test_legacy_notify_file_not_allowed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_is_allowed_path: MagicMock,
    config: ConfigType,
    domain: str,
    service: str,
    params: dict[str, str],
) -> None:
    """Test legacy notify file output not allowed."""
    assert await async_setup_component(hass, notify.DOMAIN, config)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)

    freezer.move_to(dt_util.utcnow())

    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(domain, service, params, blocking=True)
    assert f"{exc.value!r}" == "ServiceValidationError('dir_not_allowed')"


@pytest.mark.parametrize(
    ("domain", "service", "params"),
    [(notify.DOMAIN, "test", {"message": "one, two, testing, testing"})],
    ids=["legacy"],
)
@pytest.mark.parametrize(
    ("is_allowed", "config"),
    [
        (
            True,
            {
                "notify": [
                    {
                        "name": "test",
                        "platform": "file",
                        "filename": "mock_file",
                    }
                ]
            },
        ),
    ],
    ids=["allowed_but_access_failed"],
)
async def test_legacy_notify_file_exception(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_is_allowed_path: MagicMock,
    config: ConfigType,
    domain: str,
    service: str,
    params: dict[str, str],
) -> None:
    """Test legacy notify file output has exception."""
    assert await async_setup_component(hass, notify.DOMAIN, config)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, DOMAIN, config)
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


@pytest.mark.parametrize(
    ("timestamp", "data"),
    [
        (
            False,
            {
                "name": "test",
                "platform": "notify",
                "filename": "mock_file",
                "timestamp": False,
            },
        ),
        (
            True,
            {
                "name": "test",
                "platform": "notify",
                "filename": "mock_file",
                "timestamp": True,
            },
        ),
    ],
    ids=["no_timestamp", "timestamp"],
)
async def test_notify_file_entry_only_setup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    timestamp: bool,
    mock_is_allowed_path: MagicMock,
    data: dict[str, Any],
) -> None:
    """Test the notify file output."""
    filename = "mock_file"

    domain = notify.DOMAIN
    service = "send_message"
    params = {"entity_id": "notify.test", "message": "one, two, testing, testing"}
    message = params["message"]

    entry = MockConfigEntry(
        domain=DOMAIN, data=data, title=f"test [{data['filename']}]"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

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

        full_filename = os.path.join(hass.config.path(), filename)
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
    ("data", "is_allowed"),
    [
        (
            {
                "name": "test",
                "platform": "notify",
                "filename": "mock_file",
            },
            False,
        ),
    ],
    ids=["not_allowed"],
)
async def test_notify_file_not_allowed_path(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_is_allowed_path: MagicMock,
    data: dict[str, Any],
) -> None:
    """Test the notify file output is not allowed."""
    domain = notify.DOMAIN
    service = "send_message"
    params = {"entity_id": "notify.test", "message": "one, two, testing, testing"}

    entry = MockConfigEntry(
        domain=DOMAIN, data=data, title=f"test [{data['filename']}]"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)

    freezer.move_to(dt_util.utcnow())
    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(domain, service, params, blocking=True)
    assert f"{exc.value!r}" == "ServiceValidationError('dir_not_allowed')"


@pytest.mark.parametrize(
    ("data", "is_allowed"),
    [
        (
            {
                "name": "test",
                "platform": "notify",
                "filename": "mock_file",
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
    data: dict[str, Any],
) -> None:
    """Test the notify file fails."""
    domain = notify.DOMAIN
    service = "send_message"
    params = {"entity_id": "notify.test", "message": "one, two, testing, testing"}

    entry = MockConfigEntry(
        domain=DOMAIN, data=data, title=f"test [{data['filename']}]"
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
