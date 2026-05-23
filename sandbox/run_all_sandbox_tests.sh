#!/bin/bash
# Run each integration's test_init.py through the sandbox plugin and collect results.
# Output: /tmp/sandbox_test_results.csv
# macOS-compatible (no GNU grep -P, no timeout command)

RESULTS_FILE="/tmp/sandbox_test_results.csv"
ERRORS_DIR="/tmp/sandbox_test_errors"
rm -rf "$ERRORS_DIR"
mkdir -p "$ERRORS_DIR"

echo "integration,passed,failed,errors,total,status" > "$RESULTS_FILE"

# Run from the hass_client checkout next to this script.
cd "$(dirname "$0")/hass_client"

count=0
total=$(wc -l < /tmp/all_integrations.txt | tr -d ' ')

while IFS= read -r integration; do
    count=$((count + 1))
    test_file="../../tests/components/${integration}/test_init.py"

    if [ ! -f "$test_file" ]; then
        continue
    fi

    # Run with a 120-second timeout using perl (macOS compatible)
    output=$(perl -e 'alarm 120; exec @ARGV' -- \
        uv run python -m pytest \
        -p hass_client.testing.conftest_sandbox \
        "$test_file" \
        --tb=no -q --no-header 2>&1)

    exit_code=$?

    # Parse pytest output for pass/fail/error counts
    # Summary line looks like: "15 passed, 1 failed, 2 errors" or "15 passed"
    summary_line=$(echo "$output" | tail -5 | grep -E '[0-9]+ (passed|failed|error)')

    passed=$(echo "$summary_line" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+')
    failed=$(echo "$summary_line" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+')
    errors=$(echo "$summary_line" | grep -oE '[0-9]+ error' | grep -oE '[0-9]+')

    [ -z "$passed" ] && passed=0
    [ -z "$failed" ] && failed=0
    [ -z "$errors" ] && errors=0

    total_tests=$((passed + failed + errors))

    if [ $exit_code -eq 142 ] || [ $exit_code -eq 137 ]; then
        status="timeout"
        echo "$output" > "$ERRORS_DIR/${integration}.txt"
    elif [ $total_tests -eq 0 ]; then
        status="no_tests_collected"
        echo "$output" > "$ERRORS_DIR/${integration}.txt"
    elif [ $errors -gt 0 ] || [ $failed -gt 0 ]; then
        status="issues"
        echo "$output" > "$ERRORS_DIR/${integration}.txt"
    else
        status="pass"
    fi

    echo "${integration},${passed},${failed},${errors},${total_tests},${status}" >> "$RESULTS_FILE"

    # Progress update every 10 integrations
    if [ $((count % 10)) -eq 0 ]; then
        echo "[$count/$total] Last: $integration ($status - ${passed}p/${failed}f/${errors}e)"
    fi
done < /tmp/all_integrations.txt

echo ""
echo "Done! Results in $RESULTS_FILE"
echo ""
# Summary
pass_count=$(grep -c ',pass$' "$RESULTS_FILE")
issues_count=$(grep -c ',issues$' "$RESULTS_FILE")
timeout_count=$(grep -c ',timeout$' "$RESULTS_FILE")
nocollect_count=$(grep -c ',no_tests_collected$' "$RESULTS_FILE")
echo "=== SUMMARY ==="
echo "Pass: $pass_count"
echo "Issues: $issues_count"
echo "Timeout: $timeout_count"
echo "No tests collected: $nocollect_count"
