"""Run all tests for each integration through the sandbox plugin and collect results."""

import csv
import os
import re
import subprocess
import sys
import time

RESULTS_FILE = "/tmp/sandbox_test_results.csv"
ERRORS_DIR = "/tmp/sandbox_test_errors"
# Paths are relative to this file (core/sandbox/run_all_sandbox_tests.py).
_HERE = os.path.dirname(os.path.abspath(__file__))
CORE_TESTS_DIR = os.path.abspath(os.path.join(_HERE, "..", "tests", "components"))
HASS_CLIENT_DIR = os.path.join(_HERE, "hass_client")

os.makedirs(ERRORS_DIR, exist_ok=True)

# Get all integration directories that have test files
integrations = sorted([
    d for d in os.listdir(CORE_TESTS_DIR)
    if os.path.isdir(os.path.join(CORE_TESTS_DIR, d))
    and any(f.startswith("test_") and f.endswith(".py")
            for f in os.listdir(os.path.join(CORE_TESTS_DIR, d)))
])

total = len(integrations)
results = []

start_time = time.time()

for i, integration in enumerate(integrations, 1):
    test_dir = os.path.join(CORE_TESTS_DIR, integration)

    try:
        proc = subprocess.run(
            [
                "uv", "run", "python", "-m", "pytest",
                "-p", "hass_client.testing.conftest_sandbox",
                test_dir,
                "--tb=no", "-q", "--no-header",
            ],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes per integration (full directory)
            cwd=HASS_CLIENT_DIR,
        )
        output = proc.stdout + proc.stderr
        exit_code = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        output = ""
        exit_code = -1
        timed_out = True

    # Parse pytest summary line
    passed = failed = errors = 0
    for line in output.splitlines()[-10:]:
        m_passed = re.search(r'(\d+) passed', line)
        m_failed = re.search(r'(\d+) failed', line)
        m_errors = re.search(r'(\d+) error', line)
        if m_passed:
            passed = int(m_passed.group(1))
        if m_failed:
            failed = int(m_failed.group(1))
        if m_errors:
            errors = int(m_errors.group(1))

    total_tests = passed + failed + errors

    if timed_out:
        status = "timeout"
    elif total_tests == 0:
        status = "no_tests"
    elif errors == 0 and failed == 0:
        status = "pass"
    else:
        status = "issues"

    if status != "pass":
        with open(os.path.join(ERRORS_DIR, f"{integration}.txt"), "w") as ef:
            ef.write(output)

    results.append({
        "integration": integration,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": total_tests,
        "status": status,
    })

    if i % 25 == 0:
        elapsed = time.time() - start_time
        rate = i / elapsed
        eta = (total - i) / rate if rate > 0 else 0
        print(f"[{i}/{total}] {integration} -> {status} ({passed}p/{failed}f/{errors}e) | ETA: {eta/60:.0f}m")
        sys.stdout.flush()

# Write CSV
with open(RESULTS_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["integration", "passed", "failed", "errors", "total", "status"])
    writer.writeheader()
    writer.writerows(results)

# Summary
pass_count = sum(1 for r in results if r["status"] == "pass")
issues_count = sum(1 for r in results if r["status"] == "issues")
timeout_count = sum(1 for r in results if r["status"] == "timeout")
no_tests_count = sum(1 for r in results if r["status"] == "no_tests")
total_passed = sum(r["passed"] for r in results)
total_failed = sum(r["failed"] for r in results)
total_errors = sum(r["errors"] for r in results)

print(f"\n{'='*60}")
print(f"DONE - {len(results)} integrations tested (full test directories)")
print(f"{'='*60}")
print(f"Pass:           {pass_count}")
print(f"Issues:         {issues_count}")
print(f"Timeout:        {timeout_count}")
print(f"No tests:       {no_tests_count}")
print(f"")
print(f"Total tests:    {total_passed + total_failed + total_errors}")
print(f"  Passed:       {total_passed}")
print(f"  Failed:       {total_failed}")
print(f"  Errors:       {total_errors}")
print(f"\nElapsed: {(time.time() - start_time)/60:.1f} minutes")
print(f"Results: {RESULTS_FILE}")
