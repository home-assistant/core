# Preview image: official Home Assistant dev image plus the heat energy source
# changes (energy integration from core, built frontend). For testing only.
ARG BASE_IMAGE=ghcr.io/home-assistant/home-assistant:dev
FROM ${BASE_IMAGE}

COPY energy /usr/src/homeassistant/homeassistant/components/energy
COPY hass_frontend /tmp/hass_frontend

RUN \
    FRONTEND_DIR="$(python3 -c 'import hass_frontend, os; print(os.path.dirname(hass_frontend.__file__))')" \
    && cp -a /tmp/hass_frontend/. "${FRONTEND_DIR}/" \
    && rm -rf /tmp/hass_frontend \
    && python3 -m compileall -q /usr/src/homeassistant/homeassistant/components/energy
