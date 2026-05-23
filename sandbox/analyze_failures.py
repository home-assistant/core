"""Analyze sandbox test failures and produce a categorized CSV.

Categories identified from manual investigation:
1. error_type_lost - Exception subclass (ServiceNotSupported, ServiceValidationError)
   becomes generic HomeAssistantError through websocket serialization. Tests that
   check for specific exception types or translation_key/translation_domain fail.
2. service_not_registered - Service registered in sandbox but call_service goes to
   host which doesn't have it. Race condition or services that only exist locally.
3. context - Context objects don't round-trip through websocket.
4. reload - Reload/reconfig not supported in sandbox mode.
5. auth_bypass - Sandbox token bypasses user permission checks (admin-only tests).
6. teardown - Teardown errors from dual-instance event loop lifecycle.
7. timeout - Tests hang (freezer/complex async).
8. async_timeout - Config entry setup times out.
9. host_specific - Tests need host-only resources (hassio, network interfaces).
10. target_config_entry - Service calls with target.config_entry not supported through WS.
11. async_timeout_compat - Uses old async_timeout.Timeout (Python 3.14 compat issue).
12. config_entry_state - Config entry doesn't reach expected error state.
"""

import csv
import os
import re

RESULTS_CSV = "/tmp/sandbox_test_results.csv"
ERRORS_DIR = "/tmp/sandbox_test_errors"
OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TEST_RESULTS.csv")

# Manual categorization based on investigation above
MANUAL_CATEGORIES = {
    # error_type_lost: Tests expect ServiceNotSupported/ServiceValidationError but get
    # HomeAssistantError because exception type is lost in websocket serialization.
    # Also includes tests that check translation_key/translation_domain on exceptions.
    "calendar": ("error_type_lost", "Expects ServiceNotSupported, gets HomeAssistantError (21 tests)"),
    "todo": ("error_type_lost", "Expects ServiceNotSupported, gets HomeAssistantError (4 tests)"),
    "climate": ("error_type_lost", "ServiceValidationError message format differs; translation_domain lost (4f/2e)"),
    "vacuum": ("error_type_lost", "ServiceValidationError.translation_domain is None through websocket (4 tests)"),
    "fan": ("error_type_lost", "Expects ServiceValidationError, gets HomeAssistantError (1 test)"),
    "number": ("error_type_lost", "ServiceValidationError.translation_domain is None (1 test)"),
    "humidifier": ("error_type_lost", "ServiceValidationError.translation_key is None (1 test)"),
    "lock": ("error_type_lost", "ServiceValidationError message text differs (1 test)"),
    "select": ("error_type_lost", "ServiceValidationError.translation_domain is None (1 test)"),
    "water_heater": ("error_type_lost", "ServiceValidationError message text differs (1 test)"),
    "counter": ("error_type_lost", "HomeAssistantError instead of ValueError + context (2 tests)"),
    "imap": ("error_type_lost", "ServiceValidationError.translation_key is None (2 tests)"),
    "duckdns": ("error_type_lost", "ServiceValidationError.translation_key is None (4 tests)"),
    "google_assistant_sdk": ("error_type_lost", "ServiceValidationError.translation_key is None (3 tests)"),
    "google_sheets": ("error_type_lost", "ServiceValidationError with missing translation metadata (3 tests)"),
    "utility_meter": ("error_type_lost", "ServiceValidationError raised but tests expect different message (3 tests)"),
    "google": ("error_type_lost", "Expects ServiceNotSupported, gets HomeAssistantError (26 tests)"),
    "update": ("error_type_lost", "Expects specific error type, gets HomeAssistantError (1 test)"),
    "wallbox": ("error_type_lost", "HomeAssistantError raised when test expects different behavior (1 test)"),
    "shell_command": ("error_type_lost", "TemplateError becomes HomeAssistantError through websocket (1 test)"),
    "radio_frequency": ("error_type_lost", "Error message regex doesn't match formatted websocket error (2 tests)"),
    "light": ("error_type_lost", "ServiceValidationError type/context lost + context test (3 tests)"),
    "media_player": ("error_type_lost", "ServiceValidationError type lost through websocket (2 tests)"),

    # service_not_registered: Service is registered in sandbox but forward to host
    # fails because register_service hasn't completed or service is YAML-only.
    "hdmi_cec": ("service_not_registered", "Services registered locally but not on host (29 tests)"),
    "python_script": ("service_not_registered", "YAML-loaded services don't register on host (7 tests)"),
    "qwikswitch": ("service_not_registered", "async_timeout compat issue + service not found (9 tests)"),

    # auth_bypass: Sandbox token has full access, so admin-required tests don't raise.
    "backup": ("auth_bypass", "Sandbox token bypasses admin check - DID NOT RAISE Unauthorized (3 tests)"),
    "configurator": ("auth_bypass", "Sandbox token bypasses admin check (1 test)"),
    "cloud": ("auth_bypass", "Sandbox token bypasses admin check (1 test)"),
    "logger": ("auth_bypass", "Sandbox token bypasses admin check (2 tests)"),
    "homematic": ("auth_bypass", "Sandbox token bypasses admin check (1 test)"),
    "homeassistant": ("auth_bypass", "Admin check bypass + reload not supported (3f/1e)"),

    # context: Context objects not preserved through websocket round-trip.
    "input_boolean": ("context", "Context not preserved (1 test)"),
    "input_button": ("context", "Context not preserved (1 test)"),
    "switch": ("context", "Context not preserved (1 test)"),

    # context_and_reload: Both context and reload issues.
    "automation": ("context_and_reload", "Context (1) + reload (2) + trigger (1) + teardown errors (83)"),
    "input_datetime": ("context_and_reload", "Context (1) + reload (1)"),
    "input_number": ("context_and_reload", "Context (1) + reload (1)"),
    "input_select": ("context_and_reload", "Context (1) + reload (1)"),
    "input_text": ("context_and_reload", "Context (1) + reload (1)"),

    # reload: Reload not supported in sandbox.
    "timer": ("reload", "Reload not supported (1 test)"),
    "zone": ("reload", "Reload not supported (1 test)"),
    "frontend": ("reload", "Theme reload/YAML-based services not supported (4 tests)"),
    "intent_script": ("reload", "YAML reload + service execution issues (6 errors)"),

    # teardown: Event loop / fixture teardown issues from dual-instance lifecycle.
    "zwave_js": ("teardown", "All 65 errors are fixture teardown failures"),
    "teslemetry": ("teardown", "All 32 errors are fixture teardown failures"),
    "onedrive": ("teardown", "All 20 errors are fixture teardown failures"),
    "google_pubsub": ("teardown", "All 12 errors are fixture teardown failures"),
    "google_photos": ("teardown", "All 7 errors are fixture teardown failures"),
    "knx": ("teardown", "All 8 errors are fixture teardown failures"),
    "dialogflow": ("teardown", "Teardown errors (2)"),
    "file": ("teardown", "Teardown errors (2)"),
    "local_file": ("teardown", "Teardown error (1)"),
    "microsoft_face": ("teardown", "Teardown errors (2)"),
    "mobile_app": ("teardown", "Teardown error (1)"),
    "opentherm_gw": ("teardown", "Teardown errors (2)"),
    "pilight": ("teardown", "Teardown error (1)"),
    "telegram_bot": ("teardown", "Teardown errors (2)"),
    "kitchen_sink": ("teardown", "Service validation (1f) + teardown errors (8e)"),

    # async_timeout: Config entry setup or operations time out.
    "lametric": ("async_timeout", "Config entry setup/teardown times out (4 errors)"),
    "ntfy": ("async_timeout", "Config entry setup times out (9 errors)"),
    "yeelight": ("async_timeout", "Async operations timeout (17 errors)"),

    # host_specific: Tests need host-only resources.
    "hassio": ("host_specific", "Tests require supervisor connection (5 failures)"),
    "network": ("host_specific", "Tests inspect host network interfaces (6 failures)"),

    # target_config_entry: Service calls with target.config_entry not supported.
    "flume": ("target_config_entry", "target.config_entry not supported in WS call_service schema (2 tests)"),

    # config_entry_state: Config entry doesn't reach expected error state in sandbox.
    "homeassistant_connect_zbt2": ("config_entry_state", "Config entry loads when test expects SETUP_RETRY (1 test)"),
    "homeassistant_sky_connect": ("config_entry_state", "Config entry loads when test expects SETUP_RETRY (1 test)"),
    "directv": ("config_entry_state", "Config entry state mismatch (2 tests)"),
    "modern_forms": ("config_entry_state", "async_timeout compat + config entry state (2 tests)"),
    "blue_current": ("config_entry_state", "ValueError during button platform setup (1 test)"),
    "lojack": ("config_entry_state", "Unexpected entities created (1 test)"),

    # misc
    "api": ("error_type_lost", "Service call errors - response type lost through WS (2f/11e)"),
    "device_tracker": ("yaml_config", "YAML-based device tracker config not supported (2f/1e)"),
    "dynalite": ("other", "Test-specific issue (1 test)"),
    "rflink": ("other", "Test-specific issue (1 test)"),
    "schedule": ("other", "service get not working through sandbox (1 test)"),
    "google_assistant": ("other", "OAuth/token handling issue (1 test)"),
    "airthings_ble": ("teardown", "Teardown error (1)"),
    "tplink": ("other", "Credential migration issues (3 tests)"),
    "infrared": ("error_type_lost", "Error type/message lost (2 tests)"),

    # timeout
    "conversation": ("timeout", "Hangs - complex async setup"),
    "debugpy": ("timeout", "Hangs - debugger attachment"),
    "demo": ("timeout", "Hangs - large integration with many platforms"),
    "device_automation": ("timeout", "Hangs - complex automation/device setup"),
    "devolo_home_network": ("timeout", "Hangs - network device setup"),
    "ffmpeg": ("timeout", "Hangs - binary process interaction"),
    "group": ("timeout", "Hangs - complex entity group setup"),
    "media_extractor": ("timeout", "Hangs - media processing"),
    "mikrotik": ("timeout", "Hangs - network device polling"),
    "pi_hole": ("timeout", "Hangs - network polling"),
    "script": ("timeout", "Hangs - complex async script execution"),
    "sun": ("timeout", "Hangs - time-dependent calculations"),

    # no_tests
    "blueprint": ("no_tests", "No test_init.py tests"),
    "bluetooth": ("no_tests", "No test_init.py tests"),
    "pglab": ("no_tests", "No test_init.py tests"),
    "voip": ("no_tests", "No test_init.py tests"),
}

# Read results
with open(RESULTS_CSV) as f:
    reader = csv.DictReader(f)
    results = list(reader)

categorized = []
for row in results:
    integration = row["integration"]
    status = row["status"]
    passed = int(row["passed"])
    failed = int(row["failed"])
    errors = int(row["errors"])
    total = int(row["total"])

    if status == "pass":
        continue

    if integration in MANUAL_CATEGORIES:
        category, reason = MANUAL_CATEGORIES[integration]
    else:
        category = "unknown"
        reason = f"Not yet investigated ({failed}f/{errors}e)"

    categorized.append({
        "integration": integration,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": total,
        "status": status,
        "category": category,
        "reason": reason,
    })

# Write output CSV
with open(OUTPUT_CSV, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "integration", "passed", "failed", "errors", "total", "status", "category", "reason"
    ])
    writer.writeheader()
    writer.writerows(categorized)

# Print summary
from collections import Counter, defaultdict
cat_counts = Counter(r["category"] for r in categorized)
cat_integrations = defaultdict(list)
for r in categorized:
    cat_integrations[r["category"]].append(r)

print(f"Total non-passing: {len(categorized)}")
print(f"Total passing: {sum(1 for r in results if r['status'] == 'pass')}")
print(f"\n{'='*70}")
for cat, count in cat_counts.most_common():
    items = cat_integrations[cat]
    total_f = sum(r["failed"] for r in items)
    total_e = sum(r["errors"] for r in items)
    print(f"\n[{cat}] - {count} integrations ({total_f} failures, {total_e} errors)")
    print(f"  {'─'*66}")
    for r in sorted(items, key=lambda x: x["failed"] + x["errors"], reverse=True):
        print(f"  {r['integration']:30s} {r['passed']:3d}p/{r['failed']:2d}f/{r['errors']:2d}e  {r['reason']}")
print(f"\n{'='*70}")
print(f"Results written to: {OUTPUT_CSV}")
