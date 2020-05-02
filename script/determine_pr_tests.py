"""Determine tests to run."""
import argparse
import json
import pathlib
import subprocess
import sys

INTEGRATION_DIR = pathlib.Path("homeassistant/components")

IGNORE = {
    "script/determine_pr_tests.py",
    "azure-pipelines-ci.yml",
    ".pre-commit-config.yaml",
}


def get_args():
    """Get cmdline args."""
    parser = argparse.ArgumentParser(description="Determine branch testing needs")
    parser.add_argument(
        "source_branch", type=str,
    )
    parser.add_argument(
        "target_branch", type=str,
    )
    parser.add_argument(
        "output", type=str, choices=["test", "requirements"],
    )
    return parser.parse_args()


def changed_files(source_branch, target_branch):
    """Get changed files."""
    run = subprocess.run(
        [
            "git",
            "whatchanged",
            "--name-only",
            "--pretty=",
            f"{target_branch}..{source_branch}",
        ],
        capture_output=True,
    )

    if run.returncode != 0:
        raise RuntimeError(
            f"Error getting changed files between {target_branch}..{source_branch} ({run.returncode}): {run.stderr.decode()}"
        )

    return run.stdout.decode().strip().split("\n")


def determine_components(filenames):
    """Check changed files in a PR."""
    components = set()

    for filename in filenames:
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

    return components


def output_tests(components):
    """Get test output."""
    if components is None:
        return "tests"

    for component in components:
        # If it's an entity component, we need to test integration that has a platform.
        # We don't implement that logic right now and force a full test run.
        if (
            "EntityComponent"
            in (INTEGRATION_DIR / component / "__init__.py").read_text()
        ):
            return "tests"

    return " ".join(f"tests/components/{domain}" for domain in components)


def output_requirements(components):
    """Get requirements output."""
    if components is None:
        return "-r requirements_test_all.txt"

    parts = ["-r requirements_test.txt"]

    for component in components:
        manifest = json.loads(
            (INTEGRATION_DIR / component / "manifest.json").read_text()
        )
        for req in manifest.get("requirements", []):
            parts.append(req)

    return " ".join(parts)


def main():
    """Determine PR to run."""
    args = get_args()
    components = determine_components(
        changed_files(args.source_branch, args.target_branch)
    )

    if args.output == "test":
        print(output_tests(components))
        return

    if args.output == "requirements":
        print(output_requirements(components))
        return

    raise RuntimeError(f"Output {args.output} not implemented!")


if __name__ == "__main__":
    sys.exit(main())
