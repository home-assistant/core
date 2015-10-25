FROM python:3-onbuild
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

VOLUME /config

RUN pip3 install --no-cache-dir -r requirements_all.txt

# For the nmap tracker
RUN apt-get update && \
    apt-get install -y --no-install-recommends nmap net-tools && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN apt-get update && \
   apt-get install -y cython3 libudev-dev && \
   apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
   pip3 install "cython<0.23" && \
   script/build_python_openzwave

CMD [ "python", "-m", "homeassistant", "--config", "/config" ]
