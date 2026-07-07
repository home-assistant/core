"""Phase 1 spike — compare Options A and B on a 100-light area call.

Each test:

1. Spins up two ``HomeAssistant`` instances ("main" and "sandbox") wired
   through an :class:`InProcessTransport`.
2. Installs N synthetic lights inside the sandbox + N proxy entities in main.
3. Targets the proxies by area with ``light.turn_on`` and asserts the
   sandbox lights flipped on (parity check).
4. Repeats the call ``ITERATIONS`` times to measure round-trip latency.

The two functions are nearly identical — the only delta is which bridge
option the rig is built with. That is the point: same harness, swapped
protocol, apples-to-apples comparison.
"""
# Spike benchmark prints results to stdout; suppress T201 for this file.
# ruff: noqa: T201

from collections.abc import AsyncIterator
import time

from hass_client.spike.rig import SpikeRig
import pytest

from homeassistant.core import HomeAssistant

from tests.common import async_test_home_assistant

LIGHT_COUNT = 100
ITERATIONS = 5


@pytest.fixture
async def main_hass(hass: HomeAssistant) -> HomeAssistant:
    """Main HA is just the standard core fixture."""
    return hass


@pytest.fixture
async def sandbox_hass() -> AsyncIterator[HomeAssistant]:
    """Spin up a second HomeAssistant to play the sandbox role.

    Mirrors the cleanup the core ``hass`` fixture does — without
    ``async_stop(force=True)`` the import executor thread leaks and the
    conftest lingering-thread assertion trips.
    """
    async with async_test_home_assistant() as hass:
        yield hass
        await hass.async_stop(force=True)


async def _run_area_call(rig: SpikeRig) -> float:
    """Return the wall-clock time for one ``light.turn_on`` area call."""
    start = time.perf_counter()
    await rig.turn_on_area()
    return time.perf_counter() - start


async def _measure(
    option: str,
    main_hass: HomeAssistant,
    sandbox_hass: HomeAssistant,
) -> dict[str, float]:
    """Build the rig, assert correctness, time ``ITERATIONS`` calls."""
    rig = await SpikeRig.build(
        option=option,  # type: ignore[arg-type]
        count=LIGHT_COUNT,
        main_hass=main_hass,
        sandbox_hass=sandbox_hass,
    )
    try:
        # Warm-up + correctness check.
        await rig.turn_on_area()
        assert all(light.is_on for light in rig.sandbox_lights), (
            f"Option {option}: sandbox lights did not all turn on"
        )
        for entity_id in rig.proxy_entity_ids:
            state = main_hass.states.get(entity_id)
            assert state is not None, f"missing proxy state for {entity_id}"
            assert state.state == "on", (
                f"Option {option}: proxy {entity_id} reports {state.state}"
            )

        # Reset and measure.
        await rig.turn_off_area()
        timings: list[float] = []
        for _ in range(ITERATIONS):
            await rig.turn_off_area()
            timings.append(await _run_area_call(rig))
        baseline_messages = rig.transport.message_count
        baseline_bytes = rig.transport.byte_count
    finally:
        await rig.stop()

    return {
        "min": min(timings),
        "median": sorted(timings)[len(timings) // 2],
        "max": max(timings),
        "messages_total": baseline_messages,
        "bytes_total": baseline_bytes,
    }


async def test_option_a_correctness_and_latency(
    main_hass: HomeAssistant, sandbox_hass: HomeAssistant
) -> None:
    """Option A: method-forward RPC must work and stay under the budget."""
    result = await _measure("A", main_hass, sandbox_hass)
    pytest.option_a_result = result  # type: ignore[attr-defined]
    # Generous bound — Phase 1 plan target is ~50ms for 100 entities.
    assert result["median"] < 1.0, f"Option A median too slow: {result}"


async def test_option_b_correctness_and_latency(
    main_hass: HomeAssistant, sandbox_hass: HomeAssistant
) -> None:
    """Option B: action-call forwarding must work and stay under the budget."""
    result = await _measure("B", main_hass, sandbox_hass)
    pytest.option_b_result = result  # type: ignore[attr-defined]
    assert result["median"] < 1.0, f"Option B median too slow: {result}"


async def test_report_comparison() -> None:
    """Run both options in this test and emit a side-by-side report.

    This test stands on its own (no shared ``hass`` fixture) so it can
    measure both options against fresh instances without unique_id
    collisions, and the printed report has both rows in one place.
    """
    results: dict[str, dict[str, float]] = {}
    for option in ("A", "B"):
        async with (
            async_test_home_assistant() as main_hass,
            async_test_home_assistant() as sandbox_hass,
        ):
            try:
                results[option] = await _measure(option, main_hass, sandbox_hass)
            finally:
                await sandbox_hass.async_stop(force=True)
                await main_hass.async_stop(force=True)

    print("\n=== Phase 1 spike — light.turn_on area call ===")
    print(f"Entities: {LIGHT_COUNT}, iterations: {ITERATIONS}\n")
    print(
        f"{'option':<8}{'median (ms)':>14}{'min (ms)':>12}"
        f"{'max (ms)':>12}{'messages':>12}{'bytes':>10}"
    )
    for label in ("A", "B"):
        r = results[label]
        print(
            f"{label:<8}"
            f"{r['median'] * 1000:>14.2f}"
            f"{r['min'] * 1000:>12.2f}"
            f"{r['max'] * 1000:>12.2f}"
            f"{r['messages_total']:>12}"
            f"{r['bytes_total']:>10}"
        )

    # Sanity: both options should be in the same order of magnitude. If they
    # diverge by 10x, the decision doc should explain why.
    ratio = results["B"]["median"] / results["A"]["median"]
    assert 0.05 < ratio < 20, f"unexpected ratio between options: {ratio}"

    # Both options pay one round-trip per proxy on a turn_on area call.
    expected_msgs_per_call = LIGHT_COUNT
    for label in ("A", "B"):
        assert results[label]["messages_total"] >= expected_msgs_per_call * ITERATIONS
