"""Test the hassio helper."""

import os
from unittest.mock import patch

import pytest

from homeassistant.helpers.hassio import get_supervisor_ip


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        pytest.param({}, None, id="not_set"),
        pytest.param({"SUPERVISOR": "172.30.32.2"}, "172.30.32.2", id="ip"),
        pytest.param(
            {"SUPERVISOR": "172.30.32.2:80"}, "172.30.32.2", id="ip_with_port"
        ),
        pytest.param(
            {
                "SUPERVISOR": "172.30.32.2",
                "SUPERVISOR_SOCKET": "/run/supervisor/api/supervisor.sock",
            },
            "172.30.32.2",
            id="ip_with_supervisor_socket",
        ),
    ],
)
def test_get_supervisor_ip(environ: dict[str, str], expected: str | None) -> None:
    """Test the Supervisor IP is returned from the environment."""
    with patch.dict(os.environ, environ, clear=True):
        assert get_supervisor_ip() == expected
