"""Determine tests to run."""
import sys

import requests

IGNORE = {
    "script/determine_pr_tests.py",
    "azure-pipelines-ci.yml",
    ".pre-commit-config.yaml",
}


def determine(pr_id):
    """Check changed files in a PR."""
    files = requests.get(
        f"https://api.github.com/repos/home-assistant/core/pulls/{pr_id}/files"
    ).json()

    components = set()

    for changed_file in files:
        filename = changed_file["filename"]

        if filename in IGNORE:
            continue

        # Any change to core/helpers/util should test all
        if not filename.startswith("homeassistant/components/"):
            return None

        parts = filename.split("/")
        if parts[3] == "translations":
            continue

        components.add(parts[2])

    if not components:
        return None

    return " ".join(f"tests/components/{domain}" for domain in components)


def main():
    """Determine PR to run."""
    if len(sys.argv) != 2:
        print("tests")
        return

    pr_id = sys.argv[-1]

    test_suite = determine(pr_id)

    print(test_suite or "tests")


if __name__ == "__main__":
    sys.exit(main())
