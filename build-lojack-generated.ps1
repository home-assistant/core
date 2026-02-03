# Build script for LoJack component
# Generated on 2026-02-01 15:04:38

$ErrorActionPreference = "Stop"

Write-Host "Building homeassistant-lojack..." -ForegroundColor Cyan

# Build the image
docker build -f "Dockerfile.lojack-generated" -t homeassistant-lojack:latest .

if ($LASTEXITCODE -eq 0) {
    Write-Host "
Build successful!" -ForegroundColor Green
    Write-Host "Image: homeassistant-lojack:latest"
    Write-Host "
To run locally:"
    Write-Host "  docker run -p 8123:8123 -v ${PWD}/config:/config homeassistant-lojack:latest"
    Write-Host "
To push to Docker Hub:"
    Write-Host "  docker tag homeassistant-lojack:latest <username>/homeassistant-lojack:latest"
    Write-Host "  docker push <username>/homeassistant-lojack:latest"
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
