# Home Assistant Core - LoJack Integration Testing Repository

> **NOTE:** This README and associated testing files will be removed before submitting the merge request to Home Assistant Core. This repository is a fork of [home-assistant/core](https://github.com/home-assistant/core) used for developing and testing the LoJack integration.

## Overview

This repository contains the LoJack vehicle tracking integration being prepared for submission to Home Assistant Core. The integration allows Home Assistant users to track vehicles equipped with LoJack/Spireon devices.

## Repository Architecture

There are two related repositories:

| Repository | Purpose | URL |
|------------|---------|-----|
| **homeassistant_lojack** | HACS custom component (primary development) | https://github.com/devinslick/homeassistant_lojack |
| **homeassistant-core-with-lojack** | Core submission testing (this repo) | Fork of home-assistant/core |

Development happens in the HACS repo (`homeassistant_lojack`), then files are synced to this repo for Core submission testing.

## Syncing from HACS Repo

When the HACS repo is updated, sync the component files to this Core testing repo:

### Quick Sync (Recommended)

```bash
# Clone or update the HACS repo
git clone https://github.com/devinslick/homeassistant_lojack.git /tmp/homeassistant_lojack
# Or if already cloned:
# git -C /tmp/homeassistant_lojack pull

# Copy component files (from custom_components/lojack to homeassistant/components/lojack)
cp /tmp/homeassistant_lojack/custom_components/lojack/__init__.py homeassistant/components/lojack/
cp /tmp/homeassistant_lojack/custom_components/lojack/config_flow.py homeassistant/components/lojack/
cp /tmp/homeassistant_lojack/custom_components/lojack/const.py homeassistant/components/lojack/
cp /tmp/homeassistant_lojack/custom_components/lojack/device_tracker.py homeassistant/components/lojack/
cp /tmp/homeassistant_lojack/custom_components/lojack/sensor.py homeassistant/components/lojack/
cp /tmp/homeassistant_lojack/custom_components/lojack/binary_sensor.py homeassistant/components/lojack/
cp /tmp/homeassistant_lojack/custom_components/lojack/strings.json homeassistant/components/lojack/
```

### Files NOT to Sync

The following files are **Core-specific** and should NOT be overwritten from the HACS repo:

| File | Reason |
|------|--------|
| `manifest.json` | Core format differs (no `version`, `issue_tracker`; has `quality_scale`, `loggers`) |
| `quality_scale.yaml` | Core-only file for quality requirements |
| `TESTING_INSTRUCTIONS.md` | Testing documentation (Core-specific) |
| `REQUIREMENTS_CHECKLIST.md` | Core submission checklist |

### Manifest Differences

**HACS manifest** (`homeassistant_lojack`):
```json
{
  "version": "0.6.0",
  "issue_tracker": "https://github.com/devinslick/homeassistant_lojack/issues",
  "documentation": "https://github.com/devinslick/homeassistant_lojack",
  "integration_type": "device"
}
```

**Core manifest** (this repo) - DO NOT include `version` or `issue_tracker`:
```json
{
  "documentation": "https://www.home-assistant.io/integrations/lojack",
  "integration_type": "hub",
  "quality_scale": "bronze",
  "loggers": ["lojack_api"]
}
```

### After Syncing

1. Run tests to verify compatibility:
   ```bash
   pytest tests/components/lojack -v
   ```

2. Rebuild the Docker test container:
   ```powershell
   .\build-lojack-generated.ps1
   ```

3. Test interactively in the container

## Test Container

A pre-built test container is available on Docker Hub for easy testing:

**Docker Hub:** [devinslick/homeassistant-lojack](https://hub.docker.com/repository/docker/devinslick/homeassistant-lojack)

## Quick Start

### Option 1: Use Pre-built Container from Docker Hub (Recommended)

The fastest way to test the integration:

```bash
# Pull and run the test container
docker run -d \
  --name homeassistant-lojack-test \
  -p 8123:8123 \
  -v $(pwd)/config:/config \
  devinslick/homeassistant-lojack:latest
```

Access Home Assistant at http://localhost:8123

### Option 2: Build Container Locally

If you want to build the container yourself (e.g., to test local changes):

#### Prerequisites
- Docker installed and running
- PowerShell (Windows) or pwsh (Linux/macOS)

#### Using the Build Scripts

1. **Generate the Dockerfile** (if not already generated):
   ```powershell
   .\generate-ha-component-dockerfile.ps1 -ComponentPath .\homeassistant\components\lojack
   ```

2. **Build the Docker image**:
   ```powershell
   .\build-lojack-generated.ps1
   ```

3. **Run the container**:
   ```powershell
   docker run -d `
     --name homeassistant-lojack-test `
     -p 8123:8123 `
     -v ${PWD}/config:/config `
     homeassistant-lojack:latest
   ```

#### Manual Build (Alternative)

```bash
# Build using the pre-configured Dockerfile
docker build -f Dockerfile.lojack-generated -t homeassistant-lojack:latest .

# Or use the manually created Dockerfile
docker build -f Dockerfile.lojack -t homeassistant-lojack:latest .

# Run the container
docker run -d \
  --name homeassistant-lojack-test \
  -p 8123:8123 \
  -v $(pwd)/config:/config \
  homeassistant-lojack:latest
```

## Script Documentation

### generate-ha-component-dockerfile.ps1

A reusable PowerShell script that generates Dockerfiles for testing Home Assistant custom components. It reads the component's `manifest.json` and creates a properly configured Dockerfile.

**Features:**
- Automatically installs pip dependencies from `manifest.json`
- Copies component files to the correct location
- Registers the component in `integrations.json`
- Adds config flow support (if enabled)

**Usage:**
```powershell
.\generate-ha-component-dockerfile.ps1 `
  -ComponentPath .\homeassistant\components\lojack `
  -OutputPath .\Dockerfile.lojack-generated `
  -BaseImage "ghcr.io/home-assistant/home-assistant:stable" `
  -ImageName "homeassistant-lojack"
```

**Parameters:**
| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| ComponentPath | Yes | - | Path to the component directory |
| OutputPath | No | `.\Dockerfile.component` | Output path for generated Dockerfile |
| BaseImage | No | `ghcr.io/home-assistant/home-assistant:stable` | Base HA image |
| ImageName | No | `homeassistant-custom` | Name for the generated image |

### build-lojack-generated.ps1

Auto-generated build script for the LoJack component. Builds the Docker image and provides instructions for running and pushing to Docker Hub.

## Dockerfile Variants

| File | Description |
|------|-------------|
| `Dockerfile.lojack` | Manually created Dockerfile with explicit configuration |
| `Dockerfile.lojack-generated` | Auto-generated by `generate-ha-component-dockerfile.ps1` |

Both produce equivalent images - the generated version demonstrates the script's capabilities.

## Publishing to Docker Hub

After building locally, you can push to Docker Hub repository:
Replace with your own user and repository information, as needed:

```bash
# Tag with your username
docker tag homeassistant-lojack:latest devinslick/homeassistant-lojack:latest

# Login to Docker Hub if you aren't already
docker login

# Push the image
docker push devinslick/homeassistant-lojack:latest
```

## Testing the Integration

### Interactive Testing

Once the container is running:

1. Navigate to http://localhost:8123
2. Complete Home Assistant onboarding
3. Go to **Settings** > **Devices & Services**
4. Click **+ ADD INTEGRATION**
5. Search for "LoJack"
6. Enter your LoJack/Spireon credentials
7. Verify vehicles appear as device trackers

### Detailed Test Cases

See [homeassistant/components/lojack/TESTING_INSTRUCTIONS.md](homeassistant/components/lojack/TESTING_INSTRUCTIONS.md) for comprehensive testing instructions including:
- Configuration flow testing
- Error handling verification
- Device tracker attribute validation
- Integration reload/removal testing
- Automated test execution

### Running Automated Tests

```bash
# Run LoJack integration tests
pytest tests/components/lojack -v

# Run with coverage report
pytest tests/components/lojack --cov=homeassistant/components/lojack --cov-report=term-missing
```

## Container Management

```bash
# View logs
docker logs -f homeassistant-lojack-test

# Stop the container
docker stop homeassistant-lojack-test

# Remove the container
docker rm homeassistant-lojack-test

# Remove the image
docker rmi homeassistant-lojack:latest
```

## Troubleshooting

### Container won't start
- Ensure port 8123 is not in use: `lsof -i :8123` (Linux/Mac) or `netstat -ano | findstr 8123` (Windows)
- Check Docker logs: `docker logs homeassistant-lojack-test`

### Integration not appearing
- Verify the component was properly registered by checking container logs for "Added lojack to integrations.json"
- Ensure you're using the correct Docker image

### Authentication issues
- Verify your LoJack/Spireon credentials work on the official LoJack website
- Check Home Assistant logs for specific error messages

## Files to Remove Before Submission

The following files should be removed or modified before submitting the PR to Home Assistant Core:

- [ ] `README.md` (this file) - Remove entirely
- [ ] `Dockerfile.lojack` - Remove (not part of core)
- [ ] `Dockerfile.lojack-generated` - Remove (not part of core)
- [ ] `generate-ha-component-dockerfile.ps1` - Remove (not part of core)
- [ ] `build-lojack-generated.ps1` - Remove (not part of core)
- [ ] `homeassistant/components/lojack/TESTING_INSTRUCTIONS.md` - Remove (not part of core)
- [ ] `homeassistant/components/lojack/REQUIREMENTS_CHECKLIST.md` - Remove (not part of core)

## Contributing

This is a testing repository. For contributions to the LoJack integration, please wait for the official PR to Home Assistant Core.

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE.md](LICENSE.md) file for details.
