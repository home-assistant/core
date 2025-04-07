"""Test configuration for PS4."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from pyps4_2ndscreen.ddp import DEFAULT_UDP_PORT, DDPProtocol
import pytest


@pytest.fixture
def patch_load_json_object() -> Generator[MagicMock]:
    """Prevent load JSON being used."""
    with patch(
        "homeassistant.components.ps4.load_json_object", return_value={}
    ) as mock_load:
        yield mock_load


@pytest.fixture
def patch_save_json() -> Generator[MagicMock]:
    """Prevent save JSON being used."""
    with patch("homeassistant.components.ps4.save_json") as mock_save:
        yield mock_save


@pytest.fixture
def patch_get_status() -> Generator[MagicMock]:
    """Prevent save JSON being used."""
    with patch("pyps4_2ndscreen.ps4.get_status", return_value=None) as mock_get_status:
        yield mock_get_status


@pytest.fixture
def mock_ddp_endpoint() -> Generator[None]:
    """Mock pyps4_2ndscreen.ddp.async_create_ddp_endpoint."""
    protocol = DDPProtocol()
    protocol._local_port = DEFAULT_UDP_PORT
    protocol._transport = MagicMock()
    with patch(
        "homeassistant.components.ps4.async_create_ddp_endpoint",
        return_value=(None, protocol),
    ):
        yield


@pytest.fixture(autouse=True)
def patch_io(
    patch_load_json_object: MagicMock,
    patch_save_json: MagicMock,
    patch_get_status: MagicMock,
    mock_ddp_endpoint: None,
) -> None:
    """Prevent PS4 doing I/O."""
