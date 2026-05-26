#!/usr/bin/env python3
# ruff: noqa: T201, D103, BLE001
"""Helper script to resolve package details, GitHub repo, release tags, and diff links from PyPI."""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request


def get_pypi_data(package_name):
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error fetching PyPI data (HTTP {e.code}): {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network error fetching PyPI data: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error fetching PyPI data: {e}", file=sys.stderr)
        sys.exit(1)

def find_github_repo(info):
    urls = []
    if info.get("home_page"):
        urls.append(info["home_page"])
    if info.get("project_urls"):
        urls.extend(info["project_urls"].values())

    for u in urls:
        if not u:
            continue
        cleaned_url = u.replace("git+", "")
        m = re.search(r"https?://(?:www\.)?github\.com/([^/]+)/([^/]+)", cleaned_url, re.IGNORECASE)
        if m:
            owner, repo = m.groups()
            # Strip query parameters, hashes, trailing slashes, and .git extension
            repo = repo.split("?")[0].split("#")[0].split("/")[0]
            repo = repo.removesuffix(".git")
            return f"https://github.com/{owner}/{repo}"
    return None

def check_github_tag(repo_url, version):
    # Try with 'v' prefix and without
    tag_options = [f"v{version}", version]
    for tag in tag_options:
        # Check both tree and releases paths on GitHub
        for path_template in [f"tree/{tag}", f"releases/tag/{tag}"]:
            url = f"{repo_url}/{path_template}"
            try:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        return tag
            except urllib.error.HTTPError as e:
                # If it's a 404, we continue checking other tag/path options
                if e.code == 404:
                    continue
                # For non-404 HTTP errors (like 403 Forbidden/429 rate limit), exit with error to avoid false reports
                print(f"\n[ERROR] HTTP error contacting GitHub ({e.code} {e.reason}) for tag '{tag}'", file=sys.stderr)
                sys.exit(1)
            except urllib.error.URLError as e:
                # Connection or timeout error
                print(f"\n[ERROR] Network error contacting GitHub: {e.reason}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                # Unexpected exceptions
                print(f"\n[ERROR] Unexpected error verifying tag '{tag}': {e}", file=sys.stderr)
                sys.exit(1)
    return None

def main():
    parser = argparse.ArgumentParser(description="Resolve PyPI package info and GitHub release diffs.")
    parser.add_argument("package", help="Name of the PyPI package")
    parser.add_argument("old_version", help="Current version installed in Home Assistant")
    parser.add_argument("--new-version", help="Target version to bump to (defaults to latest on PyPI)")
    args = parser.parse_args()

    data = get_pypi_data(args.package)
    info = data.get("info", {})
    latest = info.get("version")

    target_version = args.new_version or latest
    github_repo = find_github_repo(info)

    print("--- RESOLVED DEPENDENCY DETAILS ---")
    print(f"Package: {args.package}")
    print(f"Current Version: {args.old_version}")
    print(f"Latest (PyPI): {latest}")
    print(f"Target Version: {target_version}")

    if github_repo:
        print(f"GitHub Repository: {github_repo}")

        # Verify tag formats on GitHub
        old_tag = check_github_tag(github_repo, args.old_version)
        new_tag = check_github_tag(github_repo, target_version)

        if not old_tag or not new_tag:
            missing_tags = []
            if not old_tag:
                missing_tags.append(args.old_version)
            if not new_tag:
                missing_tags.append(target_version)
            print(f"\n[ERROR] Could not resolve GitHub release tag for version(s): {', '.join(missing_tags)}", file=sys.stderr)
            sys.exit(1)

        changelog_url = f"{github_repo}/releases/tag/{new_tag}"
        compare_url = f"{github_repo}/compare/{old_tag}...{new_tag}"

        print("\n--- PR DOCUMENTATION LINKS ---")
        print(f"Changelog Link: {changelog_url}")
        print(f"Comparison Diff Link: {compare_url}")
    else:
        print("\n[WARNING] GitHub repository could not be resolved from PyPI metadata.")
        print("Please resolve the release notes and diff links manually.")

if __name__ == "__main__":
    main()
