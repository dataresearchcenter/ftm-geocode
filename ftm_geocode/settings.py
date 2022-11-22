import logging
import os

GEOCODERS = tuple(os.environ.get("GEOCODERS", "nominatim").split(","))
CACHE_TABLE = os.environ.get("FTMGEO_CACHE_TABLE", "ftmgeo_cache")

DATABASE_URI = os.environ.get("FTM_STORE_URI", "sqlite:///cache.db")
USER_AGENT = os.environ.get("FTMGEO_USER_AGENT", "ftm-geocode")
DEFAULT_TIMEOUT = os.environ.get("FTMGEO_DEFAULT_TIMEOUT", 10)
MIN_DELAY_SECONDS = float(os.environ.get("FTMGEO_MIN_DELAY_SECONDS", 0.1))
MAX_RETRIES = int(os.environ.get("FTMGEO_MAX_RETRIES", 5))
LOG_LEVEL = logging.getLevelName(os.environ.get("LOG_LEVEL", "info").upper())
LOG_JSON = False
