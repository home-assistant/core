FROM python:3.5
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

VOLUME /config

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# Copy build scripts
COPY script/setup_docker_prereqs script/build_python_openzwave script/build_libcec script/
RUN script/setup_docker_prereqs

# Install hass component dependencies
COPY requirements_all.txt requirements_all.txt
RUN pip3 install --no-cache-dir -r requirements_all.txt && \
    pip3 install --no-cache-dir mysqlclient psycopg2 uvloop

# Copy source
COPY . .

CMD [ "python", "-m", "homeassistant", "--config", "/config" ]
