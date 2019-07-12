FROM python:3.7

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libudev-dev \
        libavformat-dev \
        libavcodec-dev \
        libavdevice-dev \
        libavutil-dev \
        libswscale-dev \
        libswresample-dev \
        libavfilter-dev \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src

RUN git clone --depth 1 https://github.com/home-assistant/hass-release \
    && cd hass-release \
    && pip3 install -e .

WORKDIR /workspace

# Install Python dependencies from requirements.txt if it exists
COPY requirements_test_all.txt homeassistant/package_constraints.txt /workspace/
RUN pip3 install -r requirements_test_all.txt -c package_constraints.txt

# Set the default shell to bash instead of sh
ENV SHELL /bin/bash
