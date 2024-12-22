from enum import Enum
from pathlib import Path

from anystore.settings import Settings as Anystore
from geopy.geocoders import SERVICE_TO_GEOCODER
from pydantic_settings import BaseSettings, SettingsConfigDict

from ftm_geocode import __version__

anystore = Anystore()

NUTS = Path(__file__).parent.parent / "data" / "NUTS_RG_01M_2021_4326.shp.zip"
GEOCODERS = Enum("Geocoders", ((k, k) for k in SERVICE_TO_GEOCODER.keys()))


class Settings(BaseSettings):
    """
    `ftm-geocode` settings management using
    [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

    Note:
        All settings can be set via environment variables in uppercase,
        prepending `FTMGEO_` (except for those with a given prefix)

    """

    model_config = SettingsConfigDict(env_prefix="ftmgeo_")

    user_agent: str = f"ftm-geocode v{__version__}"
    """User-Agent string to use for geocoding services"""

    default_timeout: int = 10
    """Geocoder timeout"""

    min_delay_seconds: float = 0.5
    """Minimum delay between geocoding requests"""

    max_retries: int = 5
    """Maximum retries for geocoding"""

    cache_uri: str = anystore.uri
    """Cache uri (using anystore)"""

    nuts_data: Path = NUTS
    """Location for nuts shapefile data"""

    geocoders: list[GEOCODERS] = [GEOCODERS.nominatim]
    """Default geocoders to use (in order)"""
