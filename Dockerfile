FROM ghcr.io/investigativedata/libpostal:main

RUN apt-get update && apt-get -y upgrade

COPY ftm_geocode /app/ftm-geocode/ftm_geocode
COPY data /app/ftm-geocode/
COPY setup.py /app/ftm-geocode/
COPY setup.cfg /app/ftm-geocode/
COPY VERSION /app/ftm-geocode/

WORKDIR /app/ftm-geocode
RUN pip install -U pip setuptools
RUN pip install -e ".[postal]"
