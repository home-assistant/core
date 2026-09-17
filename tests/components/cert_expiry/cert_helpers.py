"""Helpers for driving cert_expiry tests against real TLS sockets and fixture certs."""

import asyncio
from collections.abc import AsyncGenerator
import contextlib
from dataclasses import dataclass
from pathlib import Path
import socket
import ssl

from .fixtures.generate import ScenarioMetadata

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCENARIOS_DIR = FIXTURES_DIR / "scenarios"


@dataclass(frozen=True)
class Scenario:
    """A certificate scenario: files to serve plus the parameters they were built with."""

    certfile: Path
    keyfile: Path
    metadata: ScenarioMetadata


def load_scenario(name: str) -> Scenario:
    """Load the scenario in fixtures/scenarios/<name>/."""
    scenario_dir = SCENARIOS_DIR / name
    return Scenario(
        certfile=scenario_dir / "cert.pem",
        keyfile=scenario_dir / "key.pem",
        metadata=ScenarioMetadata.from_json(
            (scenario_dir / "metadata.json").read_text()
        ),
    )


def server_context(scenario: Scenario, *, ciphers: str | None = None) -> ssl.SSLContext:
    """Build a server SSL context serving the scenario's certificate."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(scenario.certfile, scenario.keyfile)
    context.load_dh_params(FIXTURES_DIR / "dh_params.pem")
    if ciphers:
        context.set_ciphers(ciphers)
        # TLS 1.3 ignores set_ciphers()
        context.maximum_version = ssl.TLSVersion.TLSv1_2
    return context


@contextlib.asynccontextmanager
async def local_tls_server(context: ssl.SSLContext) -> AsyncGenerator[int]:
    """Start a real local TLS server using the given context; yield its port.

    Uses a blocking socket in a thread because asyncio.start_server aborts
    before flushing the handshake failure alert, so a cipher mismatch would
    surface as ConnectionResetError instead of an ssl.SSLError.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]

    def _accept_once() -> None:
        with contextlib.suppress(OSError), sock:
            conn, _ = sock.accept()
            with (
                contextlib.suppress(ssl.SSLError, OSError),
                conn,
                context.wrap_socket(conn, server_side=True),
            ):
                pass

    loop = asyncio.get_running_loop()
    task = loop.run_in_executor(None, _accept_once)
    try:
        yield port
    finally:
        sock.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(task, timeout=2)
