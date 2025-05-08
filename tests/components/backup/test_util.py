"""Tests for the Backup integration's utility functions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import dataclasses
import tarfile
from unittest.mock import Mock, patch

import pytest
import securetar

from homeassistant.components.backup import DOMAIN, AddonInfo, AgentBackup, Folder
from homeassistant.components.backup.util import (
    DecryptedBackupStreamer,
    EncryptedBackupStreamer,
    read_backup,
    suggested_filename,
    validate_password,
)
from homeassistant.core import HomeAssistant

from tests.common import get_fixture_path


@pytest.mark.parametrize(
    ("backup_json_content", "expected_backup"),
    [
        (
            b'{"compressed":true,"date":"2024-12-02T07:23:58.261875-05:00","homeassistant":'
            b'{"exclude_database":true,"version":"2024.12.0.dev0"},"name":"test",'
            b'"protected":true,"slug":"455645fe","type":"partial","version":2}',
            AgentBackup(
                addons=[],
                backup_id="455645fe",
                date="2024-12-02T07:23:58.261875-05:00",
                database_included=False,
                extra_metadata={},
                folders=[],
                homeassistant_included=True,
                homeassistant_version="2024.12.0.dev0",
                name="test",
                protected=True,
                size=1234,
            ),
        ),
        (
            b'{"slug":"d4b8fdc6","version":2,"name":"Core 2025.1.0.dev0",'
            b'"date":"2024-12-20T11:27:51.119062+00:00","type":"partial",'
            b'"supervisor_version":"2024.12.1.dev1803",'
            b'"extra":{"instance_id":"6b453733d2d74d2a9ae432ff2fbaaa64",'
            b'"with_automatic_settings":false},"homeassistant":'
            b'{"version":"2025.1.0.dev202412200230","exclude_database":false,"size":0.0},'
            b'"compressed":true,"protected":true,"repositories":['
            b'"https://github.com/home-assistant/hassio-addons-development","local",'
            b'"https://github.com/esphome/home-assistant-addon","core",'
            b'"https://github.com/music-assistant/home-assistant-addon",'
            b'"https://github.com/hassio-addons/repository"],"crypto":"aes128",'
            b'"folders":["share","media"],"addons":[{"slug":"core_configurator",'
            b'"name":"File editor","version":"5.5.0","size":0.0},'
            b'{"slug":"ae6e943c_remote_api","name":"Remote API proxy",'
            b'"version":"1.3.0","size":0.0}],"docker":{"registries":{}}}',
            AgentBackup(
                addons=[
                    AddonInfo(
                        name="File editor",
                        slug="core_configurator",
                        version="5.5.0",
                    ),
                    AddonInfo(
                        name="Remote API proxy",
                        slug="ae6e943c_remote_api",
                        version="1.3.0",
                    ),
                ],
                backup_id="d4b8fdc6",
                date="2024-12-20T11:27:51.119062+00:00",
                database_included=True,
                extra_metadata={
                    "instance_id": "6b453733d2d74d2a9ae432ff2fbaaa64",
                    "with_automatic_settings": False,
                },
                folders=[Folder.SHARE, Folder.MEDIA],
                homeassistant_included=True,
                homeassistant_version="2025.1.0.dev202412200230",
                name="Core 2025.1.0.dev0",
                protected=True,
                size=1234,
            ),
        ),
        # Check the backup_request_date is used as date if present
        (
            b'{"compressed":true,"date":"2024-12-01T00:00:00.000000-00:00","homeassistant":'
            b'{"exclude_database":true,"version":"2024.12.0.dev0"},"name":"test",'
            b'"extra":{"supervisor.backup_request_date":"2025-12-01T00:00:00.000000-00:00"},'
            b'"protected":true,"slug":"455645fe","type":"partial","version":2}',
            AgentBackup(
                addons=[],
                backup_id="455645fe",
                date="2025-12-01T00:00:00.000000-00:00",
                database_included=False,
                extra_metadata={
                    "supervisor.backup_request_date": "2025-12-01T00:00:00.000000-00:00"
                },
                folders=[],
                homeassistant_included=True,
                homeassistant_version="2024.12.0.dev0",
                name="test",
                protected=True,
                size=1234,
            ),
        ),
    ],
)
def test_read_backup(backup_json_content: bytes, expected_backup: AgentBackup) -> None:
    """Test reading a backup."""
    mock_path = Mock()
    mock_path.stat.return_value.st_size = 1234

    with patch("homeassistant.components.backup.util.tarfile.open") as mock_open_tar:
        mock_open_tar.return_value.__enter__.return_value.extractfile.return_value.read.return_value = backup_json_content
        backup = read_backup(mock_path)
        assert backup == expected_backup


@pytest.mark.parametrize("password", [None, "hunter2"])
def test_validate_password(password: str | None) -> None:
    """Test validating a password."""
    mock_path = Mock()

    with (
        patch("homeassistant.components.backup.util.tarfile.open"),
        patch("homeassistant.components.backup.util.SecureTarFile"),
    ):
        assert validate_password(mock_path, password) is True


@pytest.mark.parametrize("password", [None, "hunter2"])
@pytest.mark.parametrize("secure_tar_side_effect", [tarfile.ReadError, Exception])
def test_validate_password_wrong_password(
    password: str | None, secure_tar_side_effect: Exception
) -> None:
    """Test validating a password."""
    mock_path = Mock()

    with (
        patch("homeassistant.components.backup.util.tarfile.open"),
        patch(
            "homeassistant.components.backup.util.SecureTarFile",
        ) as mock_secure_tar,
    ):
        mock_secure_tar.return_value.__enter__.side_effect = secure_tar_side_effect
        assert validate_password(mock_path, password) is False


def test_validate_password_no_homeassistant() -> None:
    """Test validating a password."""
    mock_path = Mock()

    with (
        patch("homeassistant.components.backup.util.tarfile.open") as mock_open_tar,
    ):
        mock_open_tar.return_value.__enter__.return_value.extractfile.side_effect = (
            KeyError
        )
        assert validate_password(mock_path, "hunter2") is False


async def test_decrypted_backup_streamer(hass: HomeAssistant) -> None:
    """Test the decrypted backup streamer."""
    decrypted_backup_path = get_fixture_path(
        "test_backups/c0cb53bd.tar.decrypted", DOMAIN
    )
    encrypted_backup_path = get_fixture_path("test_backups/c0cb53bd.tar", DOMAIN)
    backup = AgentBackup(
        addons=[
            AddonInfo(name="Core 1", slug="core1", version="1.0.0"),
            AddonInfo(name="Core 2", slug="core2", version="1.0.0"),
        ],
        backup_id="1234",
        date="2024-12-02T07:23:58.261875-05:00",
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0.dev0",
        name="test",
        protected=True,
        size=encrypted_backup_path.stat().st_size,
    )
    expected_padding = b"\0" * 40960  # 4 x 10240 byte of padding

    async def send_backup() -> AsyncIterator[bytes]:
        f = encrypted_backup_path.open("rb")
        while chunk := f.read(1024):
            yield chunk

    async def open_backup() -> AsyncIterator[bytes]:
        return send_backup()

    decryptor = DecryptedBackupStreamer(hass, backup, open_backup, "hunter2")
    assert decryptor.backup() == dataclasses.replace(
        backup, protected=False, size=backup.size + len(expected_padding)
    )
    decrypted_stream = await decryptor.open_stream()
    decrypted_output = b""
    async for chunk in decrypted_stream:
        decrypted_output += chunk
    await decryptor.wait()

    # Expect the output to match the stored decrypted backup file, with additional
    # padding.
    decrypted_backup_data = decrypted_backup_path.read_bytes()
    assert decrypted_output == decrypted_backup_data + expected_padding


async def test_decrypted_backup_streamer_interrupt_stuck_reader(
    hass: HomeAssistant,
) -> None:
    """Test the decrypted backup streamer."""
    encrypted_backup_path = get_fixture_path("test_backups/c0cb53bd.tar", DOMAIN)
    backup = AgentBackup(
        addons=[
            AddonInfo(name="Core 1", slug="core1", version="1.0.0"),
            AddonInfo(name="Core 2", slug="core2", version="1.0.0"),
        ],
        backup_id="1234",
        date="2024-12-02T07:23:58.261875-05:00",
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0.dev0",
        name="test",
        protected=True,
        size=encrypted_backup_path.stat().st_size,
    )

    stuck = asyncio.Event()

    async def send_backup() -> AsyncIterator[bytes]:
        f = encrypted_backup_path.open("rb")
        while chunk := f.read(1024):
            await stuck.wait()
            yield chunk

    async def open_backup() -> AsyncIterator[bytes]:
        return send_backup()

    decryptor = DecryptedBackupStreamer(hass, backup, open_backup, "hunter2")
    await decryptor.open_stream()
    await decryptor.wait()


async def test_decrypted_backup_streamer_interrupt_stuck_writer(
    hass: HomeAssistant,
) -> None:
    """Test the decrypted backup streamer."""
    encrypted_backup_path = get_fixture_path("test_backups/c0cb53bd.tar", DOMAIN)
    backup = AgentBackup(
        addons=[
            AddonInfo(name="Core 1", slug="core1", version="1.0.0"),
            AddonInfo(name="Core 2", slug="core2", version="1.0.0"),
        ],
        backup_id="1234",
        date="2024-12-02T07:23:58.261875-05:00",
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0.dev0",
        name="test",
        protected=True,
        size=encrypted_backup_path.stat().st_size,
    )

    async def send_backup() -> AsyncIterator[bytes]:
        f = encrypted_backup_path.open("rb")
        while chunk := f.read(1024):
            yield chunk

    async def open_backup() -> AsyncIterator[bytes]:
        return send_backup()

    decryptor = DecryptedBackupStreamer(hass, backup, open_backup, "hunter2")
    await decryptor.open_stream()
    await decryptor.wait()


async def test_decrypted_backup_streamer_wrong_password(hass: HomeAssistant) -> None:
    """Test the decrypted backup streamer with wrong password."""
    encrypted_backup_path = get_fixture_path("test_backups/c0cb53bd.tar", DOMAIN)
    backup = AgentBackup(
        addons=[
            AddonInfo(name="Core 1", slug="core1", version="1.0.0"),
            AddonInfo(name="Core 2", slug="core2", version="1.0.0"),
        ],
        backup_id="1234",
        date="2024-12-02T07:23:58.261875-05:00",
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0.dev0",
        name="test",
        protected=True,
        size=encrypted_backup_path.stat().st_size,
    )

    async def send_backup() -> AsyncIterator[bytes]:
        f = encrypted_backup_path.open("rb")
        while chunk := f.read(1024):
            yield chunk

    async def open_backup() -> AsyncIterator[bytes]:
        return send_backup()

    decryptor = DecryptedBackupStreamer(hass, backup, open_backup, "wrong_password")
    decrypted_stream = await decryptor.open_stream()
    async for _ in decrypted_stream:
        pass

    await decryptor.wait()
    assert isinstance(decryptor._workers[0].error, securetar.SecureTarReadError)


async def test_encrypted_backup_streamer(hass: HomeAssistant) -> None:
    """Test the encrypted backup streamer."""
    decrypted_backup_path = get_fixture_path(
        "test_backups/c0cb53bd.tar.decrypted", DOMAIN
    )
    encrypted_backup_path = get_fixture_path("test_backups/c0cb53bd.tar", DOMAIN)
    backup = AgentBackup(
        addons=[
            AddonInfo(name="Core 1", slug="core1", version="1.0.0"),
            AddonInfo(name="Core 2", slug="core2", version="1.0.0"),
        ],
        backup_id="1234",
        date="2024-12-02T07:23:58.261875-05:00",
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0.dev0",
        name="test",
        protected=False,
        size=decrypted_backup_path.stat().st_size,
    )
    expected_padding = b"\0" * 40960  # 4 x 10240 byte of padding

    async def send_backup() -> AsyncIterator[bytes]:
        f = decrypted_backup_path.open("rb")
        while chunk := f.read(1024):
            yield chunk

    async def open_backup() -> AsyncIterator[bytes]:
        return send_backup()

    # Patch os.urandom to return values matching the nonce used in the encrypted
    # test backup. The backup has three inner tar files, but we need an extra nonce
    # for a future planned supervisor.tar.
    with patch("os.urandom") as mock_randbytes:
        mock_randbytes.side_effect = (
            bytes.fromhex("bd34ea6fc93b0614ce7af2b44b4f3957"),
            bytes.fromhex("1296d6f7554e2cb629a3dc4082bae36c"),
            bytes.fromhex("8b7a58e48faf2efb23845eb3164382e0"),
            bytes.fromhex("00000000000000000000000000000000"),
        )
        encryptor = EncryptedBackupStreamer(hass, backup, open_backup, "hunter2")

        assert encryptor.backup() == dataclasses.replace(
            backup, protected=True, size=backup.size + len(expected_padding)
        )

        encrypted_stream = await encryptor.open_stream()
        encrypted_output = b""
        async for chunk in encrypted_stream:
            encrypted_output += chunk
        await encryptor.wait()

    # Expect the output to match the stored encrypted backup file, with additional
    # padding.
    encrypted_backup_data = encrypted_backup_path.read_bytes()
    assert encrypted_output == encrypted_backup_data + expected_padding


async def test_encrypted_backup_streamer_interrupt_stuck_reader(
    hass: HomeAssistant,
) -> None:
    """Test the encrypted backup streamer."""
    decrypted_backup_path = get_fixture_path(
        "test_backups/c0cb53bd.tar.decrypted", DOMAIN
    )
    backup = AgentBackup(
        addons=[
            AddonInfo(name="Core 1", slug="core1", version="1.0.0"),
            AddonInfo(name="Core 2", slug="core2", version="1.0.0"),
        ],
        backup_id="1234",
        date="2024-12-02T07:23:58.261875-05:00",
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0.dev0",
        name="test",
        protected=False,
        size=decrypted_backup_path.stat().st_size,
    )

    stuck = asyncio.Event()

    async def send_backup() -> AsyncIterator[bytes]:
        f = decrypted_backup_path.open("rb")
        while chunk := f.read(1024):
            await stuck.wait()
            yield chunk

    async def open_backup() -> AsyncIterator[bytes]:
        return send_backup()

    decryptor = EncryptedBackupStreamer(hass, backup, open_backup, "hunter2")
    await decryptor.open_stream()
    await decryptor.wait()


async def test_encrypted_backup_streamer_interrupt_stuck_writer(
    hass: HomeAssistant,
) -> None:
    """Test the encrypted backup streamer."""
    decrypted_backup_path = get_fixture_path(
        "test_backups/c0cb53bd.tar.decrypted", DOMAIN
    )
    backup = AgentBackup(
        addons=[
            AddonInfo(name="Core 1", slug="core1", version="1.0.0"),
            AddonInfo(name="Core 2", slug="core2", version="1.0.0"),
        ],
        backup_id="1234",
        date="2024-12-02T07:23:58.261875-05:00",
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0.dev0",
        name="test",
        protected=True,
        size=decrypted_backup_path.stat().st_size,
    )

    async def send_backup() -> AsyncIterator[bytes]:
        f = decrypted_backup_path.open("rb")
        while chunk := f.read(1024):
            yield chunk

    async def open_backup() -> AsyncIterator[bytes]:
        return send_backup()

    decryptor = EncryptedBackupStreamer(hass, backup, open_backup, "hunter2")
    await decryptor.open_stream()
    await decryptor.wait()


async def test_encrypted_backup_streamer_random_nonce(hass: HomeAssistant) -> None:
    """Test the encrypted backup streamer."""
    decrypted_backup_path = get_fixture_path(
        "test_backups/c0cb53bd.tar.decrypted", DOMAIN
    )
    encrypted_backup_path = get_fixture_path("test_backups/c0cb53bd.tar", DOMAIN)
    backup = AgentBackup(
        addons=[
            AddonInfo(name="Core 1", slug="core1", version="1.0.0"),
            AddonInfo(name="Core 2", slug="core2", version="1.0.0"),
        ],
        backup_id="1234",
        date="2024-12-02T07:23:58.261875-05:00",
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0.dev0",
        name="test",
        protected=False,
        size=decrypted_backup_path.stat().st_size,
    )

    async def send_backup() -> AsyncIterator[bytes]:
        f = decrypted_backup_path.open("rb")
        while chunk := f.read(1024):
            yield chunk

    async def open_backup() -> AsyncIterator[bytes]:
        return send_backup()

    encryptor1 = EncryptedBackupStreamer(hass, backup, open_backup, "hunter2")
    encryptor2 = EncryptedBackupStreamer(hass, backup, open_backup, "hunter2")

    async def read_stream(stream: AsyncIterator[bytes]) -> bytes:
        output = b""
        async for chunk in stream:
            output += chunk
        return output

    # When reading twice from the same streamer, the same nonce is used.
    encrypted_output1 = await read_stream(await encryptor1.open_stream())
    encrypted_output2 = await read_stream(await encryptor1.open_stream())
    assert encrypted_output1 == encrypted_output2

    encrypted_output3 = await read_stream(await encryptor2.open_stream())
    encrypted_output4 = await read_stream(await encryptor2.open_stream())
    assert encrypted_output3 == encrypted_output4

    # Wait for workers to terminate
    await encryptor1.wait()
    await encryptor2.wait()

    # Output from the two streams should differ but have the same length.
    assert encrypted_output1 != encrypted_output3
    assert len(encrypted_output1) == len(encrypted_output3)

    # Expect the output length to match the stored encrypted backup file, with
    # additional padding.
    encrypted_backup_data = encrypted_backup_path.read_bytes()
    # 4 x 10240 byte of padding
    assert len(encrypted_output1) == len(encrypted_backup_data) + 40960
    assert encrypted_output1[: len(encrypted_backup_data)] != encrypted_backup_data


async def test_encrypted_backup_streamer_error(hass: HomeAssistant) -> None:
    """Test the encrypted backup streamer."""
    decrypted_backup_path = get_fixture_path(
        "test_backups/c0cb53bd.tar.decrypted", DOMAIN
    )
    backup = AgentBackup(
        addons=[
            AddonInfo(name="Core 1", slug="core1", version="1.0.0"),
            AddonInfo(name="Core 2", slug="core2", version="1.0.0"),
        ],
        backup_id="1234",
        date="2024-12-02T07:23:58.261875-05:00",
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0.dev0",
        name="test",
        protected=False,
        size=decrypted_backup_path.stat().st_size,
    )

    async def send_backup() -> AsyncIterator[bytes]:
        f = decrypted_backup_path.open("rb")
        while chunk := f.read(1024):
            yield chunk

    async def open_backup() -> AsyncIterator[bytes]:
        return send_backup()

    # Patch os.urandom to return values matching the nonce used in the encrypted
    # test backup. The backup has three inner tar files, but we need an extra nonce
    # for a future planned supervisor.tar.
    encryptor = EncryptedBackupStreamer(hass, backup, open_backup, "hunter2")

    with patch(
        "homeassistant.components.backup.util.tarfile.open",
        side_effect=tarfile.TarError,
    ):
        encrypted_stream = await encryptor.open_stream()
        async for _ in encrypted_stream:
            pass

    # Expect the output to match the stored encrypted backup file, with additional
    # padding.
    await encryptor.wait()
    assert isinstance(encryptor._workers[0].error, tarfile.TarError)


@pytest.mark.parametrize(
    ("name", "resulting_filename"),
    [
        ("test", "test_2025-01-30_13.42_12345678.tar"),
        ("  leading spaces", "leading_spaces_2025-01-30_13.42_12345678.tar"),
        ("trailing spaces  ", "trailing_spaces_2025-01-30_13.42_12345678.tar"),
        ("double  spaces  ", "double_spaces_2025-01-30_13.42_12345678.tar"),
    ],
)
def test_suggested_filename(name: str, resulting_filename: str) -> None:
    """Test suggesting a filename."""
    backup = AgentBackup(
        addons=[],
        backup_id="1234",
        date="2025-01-30 13:42:12.345678-05:00",
        database_included=False,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0.dev0",
        name=name,
        protected=False,
        size=1234,
    )
    assert suggested_filename(backup) == resulting_filename
