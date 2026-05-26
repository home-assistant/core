---
name: bump-dependency
description: Bumps a Python package dependency across Home Assistant Core integrations, regenerates core requirement files, compiles translation files, runs verification tests and prek lint, and prepares a pull request with proper release/compare links.
---

# Bump Python Package Dependency in Home Assistant Core

Follow these systematic steps to successfully bump a python package requirement in the repository, regenerate necessary derivative files, verify the integration, and raise a pull request.

## Gotchas & Non-Obvious Constraints

- **PR Template Integrity**: Home Assistant's Pull Request template (`.github/PULL_REQUEST_TEMPLATE.md`) MUST be preserved perfectly. **NEVER REMOVE ANY SECTION, COMMENT, OR UNCHECKED CHECKBOX.** Leave all unchecked checkboxes in place.
- **Lazy Translation Resolution**: Home Assistant tests do NOT read translations directly from `strings.json` but from the generated `translations/en.json`. After any manifest modification or dependency change, compile/regenerate translations using:
  ```bash
  uv run script/translations/develop.py --all
  ```
  Or for a specific integration:
  ```bash
  uv run python3 -m script.translations develop --integration <integration_name>
  ```
- **GitHub Tag Volatility**: Release tags on GitHub are highly inconsistent (e.g., `v1.2.3` vs `1.2.3` vs `release-1.2.3`). Always use the automated resolver `resolve_dependency.py` to check HEAD status for correct tags before hardcoding comparison URLs.

## Step-by-Step Workflow Checklist

### Phase A: Research and Plan
- [ ] **1. Identify Targets**: Note the requested target package and target version to bump.
- [ ] **2. Discover Codebase References**: Search the codebase (using `grep` or similar search tools) to find all `manifest.json` and requirements files referencing the package.
- [ ] **3. Resolve Version/Tag Details**: Run the integrated validation helper script to resolve version details, GitHub repo, release tag format, and formatted PR links:
  ```bash
  ./.agent/skills/bump-dependency/scripts/resolve_dependency.py <package> <old_version> [--new-version <new_version>]
  ```
  *(Note: If you are in a branched workspace, resolve the path to the script relative to the workspace root or the active agent skills directory).*
- [ ] **4. Plan-Validate-Execute (Draft Plan)**: Before modifying any files, write a brief, structured plan outlining the integrations to change, old version, new version, and the resolved comparison link. Show this draft plan to the user.

### Phase B: Execute and Validate (Local Changes)
- [ ] **5. Git Branch Setup**: Create a clean branch starting from the latest `upstream/dev`:
  ```bash
  git fetch upstream dev
  git checkout -b bump-<package>-to-<version> upstream/dev
  ```
- [ ] **6. Apply Bump to manifests**: Update the version constraint string in all identified `manifest.json` files (e.g., change `"package==1.0.0"` to `"package==1.1.0"`).
- [ ] **7. Regenerate Core Requirements**: Run the requirements generator to update all derivative requirements and constraint files:
  ```bash
  uv run script/gen_requirements_all.py
  ```
- [ ] **8. Validate Requirements**: Check `git diff` to ensure that only the targeted `manifest.json` files and `requirements_all.txt` (and potentially standard constraints) were modified. No unrelated files must be affected.
- [ ] **9. Regenerate Translations**: Compile/generate the translations for the modified integrations:
  ```bash
  uv run script/translations/develop.py --all
  ```
- [ ] **10. Local Venv Verification**: Install the exact targeted package version directly inside the virtual environment:
  ```bash
  uv pip install "<package>==<version>"
  ```

### Phase C: Validation Loop (Tests & Lint)
- [ ] **11. Run Integration Tests**: Execute the pytest suite for all integrations that consume the bumped package:
  ```bash
  uv run pytest tests/components/<integration_name>
  ```
  - *Validation Loop*: If tests fail, analyze the error, apply appropriate fixes, and re-run pytest until all tests pass cleanly.
- [ ] **12. Run prek Lint Checks**: Run the local prek hooks on modified files:
  ```bash
  uv run prek run
  ```
  - *Validation Loop*: If prek checks report any formatting or linting violations, fix them and repeat `uv run prek run` until it passes completely without errors.

### Phase D: User Confirmation & PR Creation
- [ ] **13. Commit Changes**: Commit the clean changes:
  ```bash
  git add <modified_files>
  git commit -m "Bump <package> to <version>"
  ```
- [ ] **14. Push Branch**: Push the local branch to your origin remote:
  ```bash
  git push origin bump-<package>-to-<version>
  ```
- [ ] **15. PR Description Preparation**: Generate the pull request body from `.github/PULL_REQUEST_TEMPLATE.md`:
  - **Proposed change**: Describe the package, old version, new version, target/source branches, and insert the resolved PyPI, changelog, and comparison diff links.
  - **Type of change**: Mark the `Dependency bump` checkbox as checked: `[x] Dependency bump`.
  - **Breaking change**: You may remove the "Breaking change" section entirely from the template.
  - **Validation checklists**: Mark `The code change is tested` checkbox as checked: `[x] The code change is tested`.
  - **Keep remaining template intact**: Do NOT remove any other commented-out blocks, headers, or unchecked checkboxes in the template.
- [ ] **16. Mandatory Review Presentation**: Format the PR proposal using the **PR Presentation Template** below and display it to the user. **Stop and wait for the user to review and explicitly confirm/approve the PR template and draft details before creating the PR.**
- [ ] **17. Raise Pull Request**: Once the user approves, create the Pull Request using the GitHub CLI:
  ```bash
  gh pr create --repo home-assistant/core --base dev --head <username>:bump-<package>-to-<version> --title "Bump <package> to <version>" --body-file <pr_body_file>
  ```

## PR Presentation Template

```markdown
### 🚀 Dependency Bump Pull Request Draft Review

- **Package**: `<package_name>` (`<old_version>` → `<new_version>`)
- **PR Title**: `Bump <package_name> to <new_version>`
- **Target Branch**: `dev`
- **Head Branch**: `<fork_username>:bump-<package_name>-to-<new_version>`

#### 🔗 PyPI & GitHub Links
- **PyPI Release**: https://pypi.org/project/<package_name>/<new_version>/
- **Changelog Link**: `<changelog_url>`
- **Comparison Diff**: `<compare_url>`

#### 📁 Modified Files
- `<list_of_modified_files>`

#### 📝 Proposed PR Body
<render the complete filled PR template body here, showing all checks and modifications for user approval>
```
