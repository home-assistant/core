# Notice:
# When updating this file, please also update virtualization/Docker/Dockerfile.dev
# This way, the development image and the production image are kept in sync.

FROM python:3.6
LABEL maintainer="Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>"

# Uncomment any of the following lines to disable the installation.
#ENV INSTALL_TELLSTICK no
#ENV INSTALL_OPENALPR no
#ENV INSTALL_FFMPEG no
#ENV INSTALL_LIBCEC no
#ENV INSTALL_PHANTOMJS no
#ENV INSTALL_SSOCR no

VOLUME /config

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# Copy source
COPY . .

# Run build scripts
RUN virtualization/Docker/setup_docker_prereqs

# Install hass component dependencies
RUN pip3 install --no-cache-dir -r requirements_all.txt -c homeassistant/package_constraints.txt && \
    pip3 install --no-cache-dir mysqlclient psycopg2 uvloop cchardet cython

CMD [ "python", "-m", "homeassistant", "--config", "/config" ]
