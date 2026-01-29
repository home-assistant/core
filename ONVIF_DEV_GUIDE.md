# ONVIF Development Guide

Quick reference for working on the ONVIF integration.

## 🚀 Local Testing Setup

### Quick Check Script ⭐
Run before pushing to catch formatting/linting issues:
```bash
./check-onvif.sh
```

### Git Pre-Push Hook ✅
Automatically runs checks before every push. Already installed!

**To bypass the hook** (not recommended):
```bash
git push --no-verify
```

### Python Tests 🧪

**Note:** Full pytest requires Python 3.14.2+ which is not yet available in pyenv.
Tests will run automatically in CI.

When Python 3.14.2 becomes available:
```bash
# Install Python 3.14.2
pyenv install 3.14.2
pyenv local 3.14.2

# Create venv
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .
pip install -r requirements_test.txt

# Run tests
pytest tests/components/onvif/test_switch.py -v
```

### Manual Testing

#### Run ruff checks:
```bash
source ~/dev/ha-test-venv/bin/activate
ruff check homeassistant/components/onvif/ tests/components/onvif/
ruff format homeassistant/components/onvif/ tests/components/onvif/
```

#### Run mypy:
```bash
source ~/dev/ha-test-venv/bin/activate
mypy homeassistant/components/onvif/
```

#### Run full prek checks (like CI):
```bash
source ~/dev/ha-test-venv/bin/activate
prek run
```

## 📁 File Structure

```
homeassistant/components/onvif/
├── __init__.py          - Integration setup, platform loading
├── config_flow.py       - Configuration UI
├── device.py            - Device abstraction & API calls
├── models.py            - Data models (Capabilities, Profile, etc)
├── switch.py            - Switch platform (relays, imaging, wiper, etc)
├── const.py             - Constants
└── strings.json         - UI translations

tests/components/onvif/
├── __init__.py          - Test fixtures & helpers
├── test_switch.py       - Switch tests
└── snapshots/           - Snapshot test data
    └── test_diagnostics.ambr
```

## 🐛 Common Issues & Solutions

### Ruff formatting flip-flops
**Problem:** Line goes back and forth between single/multiline  
**Solution:** Line length is 88 chars (including indentation). Use `ruff format` to auto-fix.

### MyPy errors
**Problem:** Type errors in your code  
**Solution:** Run `mypy homeassistant/components/onvif/` locally first. Use `Any` for dynamic SOAP/WSDL objects.

### Entities not created
**Problem:** Switch platform not loading  
**Solution:** Check that platform is added in `__init__.py`:
```python
if device.capabilities.imaging or device.capabilities.deviceio:
    device.platforms += [Platform.SWITCH]
```

### Mock tests failing
**Problem:** Tests can't find entities  
**Solution:** Ensure `setup_mock_device` in `tests/__init__.py` has correct capabilities set.

## 📚 Resources

- [Home Assistant Development](https://developers.home-assistant.io/)
- [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [ONVIF Core Spec](https://www.onvif.org/specs/core/ONVIF-Core-Specification.pdf)
- [ONVIF DeviceIO](https://www.onvif.org/specs/srv/io/ONVIF-DeviceIO-Service-Spec.pdf)

## 💡 Development Tips

1. **Always run `./check-onvif.sh` before pushing** - Catches 90% of CI failures
2. **Git pre-push hook runs automatically** - No need to remember!
3. **Use `git push --no-verify`** only in emergencies
4. **Keep commits focused and atomic** - One logical change per commit
5. **Write descriptive commit messages** - Explain the "why", not just the "what"
6. **Test with actual ONVIF cameras** when possible
7. **CI will run full tests** - Including Python version checks

## 🔄 Workflow

```bash
# 1. Make your changes
vim homeassistant/components/onvif/switch.py

# 2. Check locally (optional, but recommended)
./check-onvif.sh

# 3. Commit
git add .
git commit -m "Add relay switch support"

# 4. Push (pre-push hook runs automatically)
git push

# 5. CI runs full test suite including pytest
```

---
*Last updated: 2026-01-29*
