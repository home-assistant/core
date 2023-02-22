ARG BUILD_FROM
FROM ${BUILD_FROM}

# Synchronize with homeassistant/core.py:async_stop
ENV \
    S6_SERVICES_GRACETIME=220000

ARG QEMU_CPU

WORKDIR /usr/src

## Setup Home Assistant Core dependencies
COPY requirements.txt homeassistant/
COPY homeassistant/package_constraints.txt homeassistant/homeassistant/
RUN \
    pip3 install \
        --no-cache-dir \
        --no-index \
        --only-binary=:all: \
        --find-links "${WHEELS_LINKS}" \
        --use-deprecated=legacy-resolver \
        -r homeassistant/requirements.txt

COPY requirements_all.txt home_assistant_frontend-* home_assistant_intents-* homeassistant/
RUN \
    if ls homeassistant/home_assistant_frontend*.whl 1> /dev/null 2>&1; then \
        pip3 install \
            --no-cache-dir \
            --no-index \
            homeassistant/home_assistant_frontend-*.whl; \
    fi \
    && if ls homeassistant/home_assistant_intents*.whl 1> /dev/null 2>&1; then \
        pip3 install \
            --no-cache-dir \
            --no-index \
            homeassistant/home_assistant_intents-*.whl; \
    fi \
    && \
        LD_PRELOAD="/usr/local/lib/libjemalloc.so.2" \
        MALLOC_CONF="background_thread:true,metadata_thp:auto,dirty_decay_ms:20000,muzzy_decay_ms:20000" \
        pip3 install \
            --no-cache-dir \
            --no-index \
            --only-binary=:all: \
            --find-links "${WHEELS_LINKS}" \
            --use-deprecated=legacy-resolver \
            -r homeassistant/requirements_all.txt

## Setup Home Assistant Core
COPY . homeassistant/
RUN \
    pip3 install \
        --no-cache-dir \
        --no-index \
        --only-binary=:all: \
        --find-links "${WHEELS_LINKS}" \
        --use-deprecated=legacy-resolver \
        -e ./homeassistant \
    && python3 -m compileall \
        homeassistant/homeassistant

# Home Assistant S6-Overlay
COPY rootfs /

WORKDIR /config
