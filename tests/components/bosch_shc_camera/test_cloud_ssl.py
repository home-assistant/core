"""Test cloud_ssl.py's pinned-CA session and its HA-lifecycle cleanup wiring.

Regression coverage for the ``inject-websession`` quality_scale.yaml
research (2026-07-15): the shared Bosch cloud session must (a) still trust
the pinned ``BOSCH_CLOUD_CA_PEM`` intermediate CA, and (b) close on
``EVENT_HOMEASSISTANT_CLOSE`` -- not the earlier ``EVENT_HOMEASSISTANT_STOP``
-- matching how ``homeassistant.helpers.aiohttp_client`` closes both its own
default sessions and their connectors. Before this fix the listener was
registered on ``EVENT_HOMEASSISTANT_STOP``, so ``test_session_not_closed_by_stop_only``
below would fail (the session closed on STOP alone) and
``test_session_closes_on_homeassistant_close`` would need CLOSE to be fired
*after* an already-closed session, i.e. the STOP-then-CLOSE ordering
asserted here is the actual regression this file pins.

Deliberately overrides the package-wide ``aioclient_mock`` autouse fixture
(``conftest.py``) with a no-op: that fixture patches
``cloud_ssl.async_get_bosch_cloud_session`` itself with a mock session for
every other test in this package, which would defeat testing the real
function here.
"""

import ssl

import pytest

from homeassistant.components.bosch_shc_camera import cloud_ssl
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def aioclient_mock() -> None:
    """Disable the package-wide session patch for this file.

    This module exercises the REAL `cloud_ssl.async_get_bosch_cloud_session`,
    not the mocked one every other test file in this package relies on.
    """


async def test_session_uses_pinned_bosch_ca(hass: HomeAssistant) -> None:
    """The shared session's SSL context must still trust the pinned Bosch CA.

    Compares the pinned context's loaded CA count against a plain default
    context to prove `BOSCH_CLOUD_CA_PEM` was actually loaded, and asserts
    the VERIFY_X509_PARTIAL_CHAIN flag this module sets so the pinned
    intermediate (not a self-signed root) can anchor a chain.
    """
    plain = ssl.create_default_context()
    pinned = await cloud_ssl.async_get_bosch_cloud_ssl_context(hass)

    assert pinned is not plain
    assert pinned.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN
    assert (
        pinned.cert_store_stats()["x509_ca"] == plain.cert_store_stats()["x509_ca"] + 1
    )


async def test_session_not_closed_by_stop_only(hass: HomeAssistant) -> None:
    """EVENT_HOMEASSISTANT_STOP alone must NOT close the shared cloud session.

    Regression guard: prior to this fix, the cleanup listener was registered
    on EVENT_HOMEASSISTANT_STOP, which fires before EVENT_HOMEASSISTANT_CLOSE
    (see homeassistant/core.py's shutdown sequence) -- closing the session
    here would have torn it down while other integrations' stop-phase
    cleanup could still be running.
    """
    session = await cloud_ssl.async_get_bosch_cloud_session(hass)
    assert not session.closed

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert not session.closed

    # Clean up so this test doesn't leak an open session/connector.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()


async def test_session_closes_on_homeassistant_close(hass: HomeAssistant) -> None:
    """EVENT_HOMEASSISTANT_CLOSE must close the shared cloud session."""
    session = await cloud_ssl.async_get_bosch_cloud_session(hass)
    assert not session.closed

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert session.closed
