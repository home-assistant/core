<#
.SYNOPSIS
    Generates a Dockerfile for testing Home Assistant custom components.

.DESCRIPTION
    This script reads a Home Assistant component's manifest.json and generates
    a Dockerfile that properly integrates the component into the official
    Home Assistant image, including:
    - Installing pip dependencies
    - Copying component files
    - Registering in integrations.json
    - Adding to config_flows.py (if config_flow enabled)

.PARAMETER ComponentPath
    Path to the component directory (must contain manifest.json)

.PARAMETER OutputPath
    Path for the generated Dockerfile (default: ./Dockerfile.component)

.PARAMETER BaseImage
    Base Home Assistant image (default: ghcr.io/home-assistant/home-assistant:stable)

.PARAMETER ImageName
    Name for the generated image (default: homeassistant-custom)

.EXAMPLE
    .\generate-ha-component-dockerfile.ps1 -ComponentPath .\homeassistant\components\lojack

.EXAMPLE
    .\generate-ha-component-dockerfile.ps1 -ComponentPath .\homeassistant\components\mycomponent -ImageName myha -OutputPath .\Dockerfile.mycomponent
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ComponentPath,

    [Parameter(Mandatory=$false)]
    [string]$OutputPath = ".\Dockerfile.component",

    [Parameter(Mandatory=$false)]
    [string]$BaseImage = "ghcr.io/home-assistant/home-assistant:stable",

    [Parameter(Mandatory=$false)]
    [string]$ImageName = "homeassistant-custom"
)

# Resolve paths
$ComponentPath = Resolve-Path $ComponentPath -ErrorAction Stop
$ManifestPath = Join-Path $ComponentPath "manifest.json"

# Validate component
if (-not (Test-Path $ManifestPath)) {
    Write-Error "manifest.json not found in $ComponentPath"
    exit 1
}

# Read manifest
$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$domain = $manifest.domain
$name = $manifest.name
$hasConfigFlow = $manifest.config_flow -eq $true
$requirements = $manifest.requirements
$integrationType = if ($manifest.integration_type) { $manifest.integration_type } else { "hub" }
$iotClass = if ($manifest.iot_class) { $manifest.iot_class } else { "cloud_polling" }
$qualityScale = if ($manifest.quality_scale) { $manifest.quality_scale } else { "bronze" }

Write-Host "Component: $name ($domain)" -ForegroundColor Cyan
Write-Host "  Config Flow: $hasConfigFlow"
Write-Host "  Integration Type: $integrationType"
Write-Host "  IoT Class: $iotClass"
Write-Host "  Requirements: $($requirements -join ', ')"

# Calculate relative path for COPY command
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$relativeComponentPath = $ComponentPath.Replace("$scriptDir\", "").Replace("\", "/")

# If ComponentPath is absolute and not relative to script dir, use just the component folder structure
if ($relativeComponentPath -eq $ComponentPath) {
    # Try to find homeassistant/components in the path
    if ($ComponentPath -match "homeassistant[/\\]components[/\\]") {
        $relativeComponentPath = $ComponentPath -replace ".*?(homeassistant[/\\]components[/\\])", "homeassistant/components/"
        $relativeComponentPath = $relativeComponentPath.Replace("\", "/")
    } else {
        Write-Error "Component path must be under homeassistant/components/"
        exit 1
    }
}

# Build pip install command
$pipInstallCmd = ""
if ($requirements -and $requirements.Count -gt 0) {
    $reqString = ($requirements | ForEach-Object { "`"$_`"" }) -join " "
    $pipInstallCmd = @"

# Install component dependencies
RUN pip3 install --no-cache-dir $($requirements -join ' ')
"@
}

# Build integrations.json update command
$integrationData = @{
    name = $name
    integration_type = $integrationType
    config_flow = $hasConfigFlow
    iot_class = $iotClass
}
if ($qualityScale) {
    $integrationData.quality_scale = $qualityScale
}
# Convert to JSON, escape quotes, and fix booleans for Python (true->True, false->False)
$integrationJson = ($integrationData | ConvertTo-Json -Compress).Replace('"', '\"').Replace(':true', ':True').Replace(':false', ':False')

$integrationsJsonCmd = @"

# Register $domain in Home Assistant's integrations.json
RUN python3 -c "\
import json; \
f = open('/usr/src/homeassistant/homeassistant/generated/integrations.json', 'r'); \
data = json.load(f); \
f.close(); \
data['integration']['$domain'] = $integrationJson; \
f = open('/usr/src/homeassistant/homeassistant/generated/integrations.json', 'w'); \
json.dump(data, f); \
f.close(); \
print('Added $domain to integrations.json')"
"@

# Build config_flows.py update command (only if config_flow is enabled)
$configFlowCmd = ""
if ($hasConfigFlow) {
    # Find an insertion point - use a known integration that comes before this domain alphabetically
    # Common integrations that exist in all HA versions, sorted: local_calendar, local_file, local_todo, logger, logbook
    # For most integrations starting with 'l' or later, 'local_todo' is a safe insertion point
    # For earlier letters, we use 'input_boolean' or 'homeassistant'
    $insertAfter = "local_todo"
    if ($domain -lt "local_todo") {
        if ($domain -lt "input_boolean") {
            $insertAfter = "homeassistant"
        } else {
            $insertAfter = "input_boolean"
        }
    }

    $configFlowCmd = @"

# Add $domain to config_flows.py (insert after $insertAfter alphabetically)
RUN sed -i '/\"$insertAfter\",/a\        \"$domain\",' /usr/src/homeassistant/homeassistant/generated/config_flows.py && \
    echo "Added $domain to config_flows.py"
"@
}

# Generate Dockerfile
$dockerfile = @"
# Auto-generated Dockerfile for Home Assistant with $name component
# Generated on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
#
# Build: docker build -f $([System.IO.Path]::GetFileName($OutputPath)) -t $ImageName .
# Run:   docker run -p 8123:8123 -v ./config:/config $ImageName

FROM $BaseImage

LABEL maintainer="auto-generated"
LABEL description="Home Assistant with $name custom component"
LABEL component.domain="$domain"
LABEL component.name="$name"
$pipInstallCmd

# Copy the $domain component
COPY $relativeComponentPath /usr/src/homeassistant/homeassistant/components/$domain

# Ensure proper permissions
RUN chmod -R 755 /usr/src/homeassistant/homeassistant/components/$domain
$integrationsJsonCmd
$configFlowCmd
"@

# Write Dockerfile
$dockerfile | Out-File -FilePath $OutputPath -Encoding utf8 -NoNewline
Write-Host "`nGenerated Dockerfile: $OutputPath" -ForegroundColor Green

# Generate build script
$buildScriptPath = $OutputPath -replace "Dockerfile\.", "build-"
$buildScriptPath = $buildScriptPath -replace "\.dockerfile$", ""
$buildScriptPath = "$buildScriptPath.ps1"

$buildScript = @"
# Build script for $name component
# Generated on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

`$ErrorActionPreference = "Stop"

Write-Host "Building $ImageName..." -ForegroundColor Cyan

# Build the image
docker build -f "$([System.IO.Path]::GetFileName($OutputPath))" -t ${ImageName}:latest .

if (`$LASTEXITCODE -eq 0) {
    Write-Host "`nBuild successful!" -ForegroundColor Green
    Write-Host "Image: ${ImageName}:latest"
    Write-Host "`nTo run locally:"
    Write-Host "  docker run -p 8123:8123 -v `${PWD}/config:/config ${ImageName}:latest"
    Write-Host "`nTo push to Docker Hub:"
    Write-Host "  docker tag ${ImageName}:latest <username>/${ImageName}:latest"
    Write-Host "  docker push <username>/${ImageName}:latest"
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
"@

$buildScript | Out-File -FilePath $buildScriptPath -Encoding utf8
Write-Host "Generated build script: $buildScriptPath" -ForegroundColor Green

Write-Host "`n=== Next Steps ===" -ForegroundColor Yellow
Write-Host "1. Review the generated Dockerfile: $OutputPath"
Write-Host "2. Build the image: .\$([System.IO.Path]::GetFileName($buildScriptPath))"
Write-Host "   Or: docker build -f $([System.IO.Path]::GetFileName($OutputPath)) -t $ImageName ."
Write-Host "3. Test locally: docker run -p 8123:8123 -v `${PWD}/config:/config $ImageName"
