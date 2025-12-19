# Wire Changes Documentation - My Smart Homes Fork

This document details the **custom modifications (wire changes)** that differentiate the **My Smart Homes fork** from the **official Home Assistant core**.

## Overview

These changes represent the delta between:
- **Upstream:** `home-assistant/core` (official Home Assistant)
- **Fork:** `my-smart-homes/core-updated` (My Smart Homes custom version)

**Fork Point:** Commit `1cf809f8fce` (core-patch-f-33)

The main changes focus on implementing custom functionality for the My Smart Homes (MSH) deployment, specifically around internal URL updates, public IP detection, and reverse proxy configuration.

---

## Chronological Changes

### 1. Initial Custom Utilities Setup (Earlier commits)
**Files Modified:** `homeassistant/msh_utils.py`
- Created custom utilities module for MSH-specific functionality
- Implemented Firebase integration for configuration management
- Added reverse proxy client functionality

### 2. Reverse Proxy Port Update (Commit: `92d01f8ce8f`)
**Date:** Tue Apr 8 19:56:15 2025 +0545  
**Author:** Bhesh Raj Thapa  
**Commit:** `92d01f8ce8f5f7e0c1046079f03c99fb791f1ad6`

**Changes in `homeassistant/msh_utils.py`:**
- Updated reverse proxy server port from `8002` to `80`
- Modified frpc (fast reverse proxy client) command configuration
- Target server: `home1.msh.srvmysmarthomes.us`

```python
# Changed from:
"-P", "8002"
# To:
"-P", "80"
```

### 3. Internal URL Update on Startup (Commit: `7489b2dc4bc`)
**Date:** Fri May 9 17:02:57 2025 +0545  
**Author:** Bhesh Raj Thapa  
**Commit:** `7489b2dc4bcd3968fb626c3fec7a51c8f343a7cd`

**Files Modified:**
- `homeassistant/__main__.py` (77 lines added, 12 deleted)
- `homeassistant/components/onboarding/views.py` (43 lines added)

#### Changes in `__main__.py`:
1. **Added imports:**
   - `requests`
   - `socket`
   - `aiohttp`

2. **Implemented `on_startup_update_internal_url()` function:**
   - Gets VM's IP address using `socket.gethostname()` and `socket.gethostbyname()`
   - Retrieves server ID from configuration file via `msh_utils`
   - Constructs internal URL: `http://{ip_address}:8123`
   - Posts update to Firebase Function: `https://us-central1-fourth-return-421315.cloudfunctions.net/updateInternalUrl`
   - Payload includes: `serverId` and `newInternalUrl`

3. **Threading implementation:**
   - Created daemon thread to run the update function on startup
   - Moved existing custom threads (ring dashboard, reverse proxy) to run after this function

#### Changes in `onboarding/views.py`:
1. **Added imports:**
   - `EVENT_HOMEASSISTANT_STARTED`
   - `async_get_clientsession`
   - `HomeAssistant`, `callback`
   - `msh_utils`

2. **Implemented `_update_internal_url()` function:**
   - Listens for `EVENT_HOMEASSISTANT_STARTED` event
   - Extracts internal URL from `hass.http.api.base_url`
   - Posts to Firebase function to update internal URL
   - Uses async HTTP session for non-blocking operation

### 4. Cleanup: Removed Duplicate Functionality (Commit: `9867e513ab8`)
**Date:** Fri May 9 17:26:55 2025 +0545  
**Author:** Bhesh Raj Thapa  
**Commit:** `9867e513ab8dc4f37caa5063348970cef5c01ba8`

**Changes in `homeassistant/components/onboarding/views.py`:**
- Removed the duplicate imports and functionality added in the previous commit
- Deleted 6 lines of unused imports related to internal URL update
- Kept the functionality only in `__main__.py` to avoid duplication

### 5. Fix Internal IP Issue (Commit: `666c7800ad7`)
**Date:** Thu Jul 10 01:46:06 2025 +0600  
**Author:** fuadnafiz98  
**Commit:** `666c7800ad7d5d58970720ef879e17dce07847e7`

**Files Modified:** `homeassistant/__main__.py` (76 lines added, 15 deleted)

#### Major Enhancement: Robust Public IP Detection

**Problem Solved:**
- Original implementation used `socket.gethostbyname(socket.gethostname())` which doesn't work correctly in Docker containers
- Docker containers typically report localhost or internal container IPs, not the actual public/egress IP

**Solution Implemented:**

1. **Added `get_public_internet_ip()` async function with:**
   - Multiple fallback IP services for reliability
   - Retry mechanism with exponential backoff
   - Comprehensive error handling
   - Timeout protection

2. **Public IP Services (in priority order):**
   ```python
   PUBLIC_IP_SERVICES = [
       "https://ident.me",
       "https://api.ipify.org",
       "https://icanhazip.com",
       "https://checkip.amazonaws.com",
   ]
   ```

3. **Features:**
   - **Max retries:** 3 attempts per service
   - **Initial delay:** 1 second with exponential backoff (1s, 2s, 4s)
   - **Timeout:** 5 seconds per request
   - **Fallback:** Returns `127.0.0.1` if all services fail

4. **Error Handling:**
   - `asyncio.TimeoutError` - for request timeouts
   - `aiohttp.ClientConnectionError` - for network issues
   - `aiohttp.ClientResponseError` - for HTTP errors
   - Generic `Exception` - for unexpected errors

5. **Logging:**
   - Added proper `logging` module import
   - Logs each attempt, success, and failure
   - Different log levels: `info`, `warning`, `error`

6. **Updated `on_startup_update_internal_url()`:**
   - Replaced `socket.gethostbyname()` with `await get_public_internet_ip()`
   - Now correctly detects public IP even in Docker/containerized environments
   - More reliable for cloud deployments and NAT scenarios

---

## Summary of Wire Changes

### What Makes This Fork Different from Official Home Assistant:

**Core Custom Files Added:**
- `homeassistant/msh_utils.py` - **NEW FILE** (461 lines) - MSH-specific utilities and Firebase integration
- `homeassistant/msh_large_strings.py` - **NEW FILE** - Large string constants for MSH features

**Core Files Modified:**
- `homeassistant/__main__.py` - Startup hooks for MSH functionality (+131 lines)
- `homeassistant/auth/providers/homeassistant.py` - Authentication customizations (+29 lines)
- `homeassistant/config.py` - Configuration management changes
- `homeassistant/package_constraints.txt` - MSH-specific dependencies

**Build & CI Workflow Changes:**
- `.github/workflows/builder.yml` - Custom build pipeline
- `.github/workflows/ci.yaml` - Continuous integration customizations
- Other workflow files for MSH deployment automation

**Translation Files:**
- Hundreds of component translation files added/modified (shown in diff stat)

### Key Functional Modifications:

1. **Reverse Proxy Configuration** (`msh_utils.py`)
   - Updated frpc port from 8002 to 80
   - Enables proper HTTP communication through reverse proxy

2. **Internal URL Auto-Update** (`__main__.py`)
   - Automatic detection of VM's public IP address
   - Firebase Function integration for centralized URL management
   - Supports Docker and containerized deployments
   - Robust multi-service IP detection with failover

3. **Enhanced Reliability** (Progressive improvements)
   - Started with basic socket-based IP detection
   - Evolved to external service-based public IP detection
   - Implemented retry logic and multiple fallback services
   - Added comprehensive logging and error handling

### Integration Points:

- **Firebase Functions:** `updateInternalUrl` endpoint
- **Custom Module:** `homeassistant/msh_utils.py` for shared utilities
- **Startup Hooks:** Daemon threads in `main()` function
- **Configuration Storage:** YAML-based config file access

### Architecture Pattern:

```
Home Assistant Startup
    ↓
on_startup_update_internal_url() [Daemon Thread]
    ↓
get_public_internet_ip() [Async with Retry]
    ↓
Multiple Public IP Services (Fallback Chain)
    ↓
Construct Internal URL (http://{public_ip}:8123)
    ↓
POST to Firebase Function
    ↓
Update Server Registry with Internal URL
```

---

## Files Affected

1. `homeassistant/__main__.py` - Main entry point modifications
2. `homeassistant/msh_utils.py` - Custom utilities and reverse proxy
3. `homeassistant/components/onboarding/views.py` - Temporarily modified, then cleaned up

---

## Purpose

These changes enable the My Smart Homes infrastructure to:
- Track and update internal URLs of deployed Home Assistant instances
- Support dynamic IP environments and Docker deployments
- Maintain connectivity through reverse proxy tunneling
- Centralize server management via Firebase Functions
- Provide reliable public IP detection with multiple fallback mechanisms

---

## Compatibility Notes

- All changes are in custom code paths that don't interfere with core Home Assistant functionality
- Uses daemon threads to avoid blocking main startup sequence
- Gracefully handles failures without breaking Home Assistant startup
- Compatible with both bare metal and containerized deployments

---

## Next Steps for Maintaining Fork

When syncing with the upstream fork:

1. **Identify Merge Base:**
   ```bash
   git merge-base upstream/dev sync-fork
   # Current fork point: 1cf809f8fce (core-patch-f-33)
   ```

2. **Preserve Custom Files:**
   - `homeassistant/msh_utils.py` (never exists in upstream)
   - `homeassistant/msh_large_strings.py` (never exists in upstream)

3. **Carefully Merge Modified Files:**
   - `homeassistant/__main__.py` - Contains startup threading logic
   - `homeassistant/auth/providers/homeassistant.py` - Custom auth changes
   - `homeassistant/config.py` - Configuration handling

4. **Resolve Conflicts:** 
   - If upstream modifies `__main__.py`, carefully merge the custom threading logic
   - Pay special attention to import statements and function call order

5. **Test Thoroughly:** 
   - Verify internal URL updates still work after merge
   - Test reverse proxy connectivity
   - Validate Firebase integration

6. **Review Dependencies:** 
   - Ensure `aiohttp`, `requests`, and `socket` remain available
   - Check if upstream changes affect custom package constraints

### Viewing All Changes:
```bash
# See all modified files
git diff upstream/dev..HEAD --stat

# See specific file changes
git diff upstream/dev..HEAD -- homeassistant/__main__.py

# List all commits unique to fork
git log upstream/dev..HEAD --oneline
```

---

**Document Created:** 2025-12-19  
**Last Updated:** 2025-12-19  
**Maintained By:** My Smart Homes Development Team

---

## Appendix: Understanding the Fork

```
Official Home Assistant (upstream/dev)
    ↓
    1cf809f8fce (fork point: core-patch-f-33)
    ↓
    [25+ custom commits]
    ↓
My Smart Homes Fork (sync-fork branch)
    ↓
Custom Features:
  • Public IP detection with failover
  • Internal URL auto-update to Firebase
  • Reverse proxy client (frpc)
  • MSH utilities module
  • Custom authentication
  • Ring dashboard integration
```

This fork maintains compatibility with Home Assistant while adding MSH-specific cloud integration features.
