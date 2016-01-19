FROM python:3.4
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

VOLUME /config

WORKDIR /usr/src/app

# Copy source
COPY . .

# For the nmap tracker
RUN apt-get update && \
    apt-get install -y --no-install-recommends nmap net-tools cython3 libudev-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \

RUN pip3 install "cython<0.23" && \
    script/build_python_openzwave && \
    pip3 install --no-cache-dir -r requirements_all.txt

EXPOSE 8123
CMD [ "python", "-m", "homeassistant", "--config", "/config" ]
