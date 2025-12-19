# CI/CD PyPI Upload Analysis

## Current Status: ⚠️ PARTIALLY CONFIGURED

The CI/CD pipeline is **configured to upload to PyPI**, but there are **critical requirements** that must be met for it to work correctly.

---

## How It Works

### Workflow File: `.github/workflows/builder.yml`

### Triggers
The PyPI upload job runs when:
1. **Manual trigger**: `workflow_dispatch` (manual run from GitHub UI)
2. **Release published**: When you create a GitHub release
3. **Scheduled**: Daily at 2 AM UTC (`cron: "0 2 * * *"`)

### PyPI Upload Job Configuration

```yaml
build_pypi:
  name: Build PyPi package
  environment: ${{ needs.init.outputs.channel }}
  needs: ["init", "build_base"]
  runs-on: ubuntu-latest
  if: needs.init.outputs.publish == 'true'  # ⚠️ Only runs if publish flag is true
  steps:
    - Checkout repository
    - Create config_core_secrets.py from secrets
    - Set up Python 3.13
    - Download translations
    - Build package with `python -m build`
    - Upload to PyPI with twine
```

---

## ✅ What's Already Configured

1. **Build Process**: Uses `python -m build` (correct)
2. **Twine Installation**: Fixed in commit `a955c7f3159` to install twine
3. **Upload Method**: Changed from `pypa/gh-action-pypi-publish` to manual `twine upload`
4. **Skip Existing**: Uses `--skip-existing` flag to avoid re-upload errors
5. **Authentication**: Uses token-based auth (`__token__` username)

---

## ❌ Required Secrets (MUST BE CONFIGURED)

### 1. `TWINE_TOKEN` (Critical)
**Purpose**: PyPI API token for authentication

**How to get it:**
1. Go to https://pypi.org (or https://test.pypi.org for testing)
2. Login to your account
3. Go to Account Settings → API Tokens
4. Click "Add API token"
5. Name: `my-smart-homes-github-ci`
6. Scope: Select "Entire account" or specific project
7. Copy the token (starts with `pypi-AgEIcHlwaS5vcmc...`)

**How to add to GitHub:**
1. Go to repository: https://github.com/my-smart-homes/core-updated
2. Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Name: `TWINE_TOKEN`
5. Value: Paste the PyPI token
6. Click "Add secret"

### 2. `CONFIG_CORE_SECRETS_BASE64` (Required for MSH)
**Purpose**: Base64-encoded version of `config_core_secrets.py`

**Why needed**: Your custom code references this file in `msh_utils.py`:
```python
from . import config_core_secrets as ccs
```

**How to create:**
```bash
# Encode the file
base64 -w 0 homeassistant/config_core_secrets.py > config_core_secrets_base64.txt

# Or if file doesn't exist, create a dummy one first:
echo "# Config secrets placeholder" > homeassistant/config_core_secrets.py
base64 -w 0 homeassistant/config_core_secrets.py
```

**How to add to GitHub:**
1. Same steps as TWINE_TOKEN
2. Name: `CONFIG_CORE_SECRETS_BASE64`
3. Value: Paste the base64 string
4. Click "Add secret"

---

## ⚠️ Publish Condition

The job has a critical condition:
```yaml
if: needs.init.outputs.publish == 'true'
```

This means the job only runs when the `init` job determines it should publish.

### When does `publish` become `true`?

The `init` job uses:
```yaml
- name: Get version
  id: version
  uses: home-assistant/actions/helpers/version@master
  with:
    type: ${{ env.BUILD_TYPE }}
```

This action likely checks:
- Is this a tagged release?
- Is this the default branch?
- Is the version new/unpublished?

**To ensure publishing works:**
1. **Create a GitHub Release** with a version tag (e.g., `v20241018.2`)
2. **Or** manually trigger workflow and ensure version is properly set
3. **Check workflow logs** to see why `publish` might be `false`

---

## 🔍 Testing the Upload

### Option 1: Test with TestPyPI First (Recommended)

1. Create a TestPyPI account: https://test.pypi.org/account/register/
2. Get TestPyPI API token
3. Modify `.github/workflows/builder.yml` temporarily:
   ```yaml
   - name: Upload package
     shell: bash
     run: |
       export TWINE_USERNAME="__token__"
       export TWINE_PASSWORD="${{ secrets.TEST_PYPI_TOKEN }}"
       twine upload --repository testpypi dist/* --skip-existing
   ```
4. Add `TEST_PYPI_TOKEN` secret to GitHub
5. Trigger workflow manually
6. Check https://test.pypi.org/project/my-smart-homes/

### Option 2: Manual Local Test

```bash
# Build package (already done)
./venv/bin/python -m build

# Install twine
./venv/bin/pip install twine

# Upload to TestPyPI
./venv/bin/twine upload --repository testpypi dist/* --skip-existing

# Upload to real PyPI (when ready)
./venv/bin/twine upload dist/* --skip-existing
```

---

## 📋 Pre-Upload Checklist

Before the CI/CD can successfully upload to PyPI:

- [ ] PyPI account created
- [ ] Project name `my_smart_homes` is available on PyPI
- [ ] `TWINE_TOKEN` secret added to GitHub repository
- [ ] `CONFIG_CORE_SECRETS_BASE64` secret added to GitHub repository
- [ ] Version in `pyproject.toml` is unique (not already on PyPI)
- [ ] GitHub release created (triggers the workflow)
- [ ] Workflow runs and `publish` condition is met

---

## 🚨 Common Issues

### 1. "File already exists" Error
**Solution**: Package version already uploaded. Bump version in `pyproject.toml`

### 2. "Invalid authentication credentials"
**Solution**: Check `TWINE_TOKEN` is correct and not expired

### 3. "Project name conflicts"
**Solution**: Package name `my_smart_homes` might be taken. Check:
```bash
pip search my_smart_homes
# Or visit: https://pypi.org/project/my-smart-homes/
```

### 4. `publish == 'false'`
**Solution**: 
- Create a proper GitHub release with version tag
- Check `init` job logs for why publish was disabled
- May need to adjust version detection logic

### 5. Missing `config_core_secrets.py`
**Solution**: Add the `CONFIG_CORE_SECRETS_BASE64` secret

---

## 🎯 Recommended Next Steps

1. **Register on PyPI**: https://pypi.org/account/register/
2. **Check name availability**: https://pypi.org/project/my-smart-homes/
3. **Generate PyPI token**: Account Settings → API tokens
4. **Add GitHub secrets**: Both `TWINE_TOKEN` and `CONFIG_CORE_SECRETS_BASE64`
5. **Create GitHub release**: Tag version `v20241018.2`
6. **Monitor workflow**: Watch Actions tab for success/failure
7. **Verify upload**: Check https://pypi.org/project/my-smart-homes/

---

## 📊 Workflow Status Check

To verify if secrets are configured:
```bash
# This won't show values, but confirms they exist
gh secret list
```

To trigger manually:
1. Go to: https://github.com/my-smart-homes/core-updated/actions
2. Select "Build images" workflow
3. Click "Run workflow" dropdown
4. Select branch: `sync-fork`
5. Click "Run workflow"

---

## Summary

**Will CI/CD upload to PyPI?**
- ✅ **Code is correct**: The workflow is properly configured
- ⚠️ **Secrets needed**: Must add `TWINE_TOKEN` and `CONFIG_CORE_SECRETS_BASE64`
- ⚠️ **Publish condition**: Must trigger via GitHub release or ensure `publish` flag is true
- ⚠️ **PyPI account**: Must have account and project name available

**Once secrets are configured and a release is created, yes, it will automatically upload to PyPI!**

---

**Document Created**: 2025-12-19  
**Last Updated**: 2025-12-19  
**Status**: Waiting for GitHub secrets configuration
