"""Tests for the Backup integration's utility functions."""

from __future__ import annotations

import tarfile
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.backup import AddonInfo, AgentBackup, Folder
from homeassistant.components.backup.util import read_backup, validate_password


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
