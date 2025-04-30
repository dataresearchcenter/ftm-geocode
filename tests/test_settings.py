from ftm_geocode import __version__
from ftm_geocode.settings import GEOCODERS, Settings


def test_settings():
    settings = Settings()
    assert settings.user_agent == f"ftm-geocode v{__version__}"
    assert settings.default_timeout == 10
    assert settings.min_delay_seconds == 0.5
    assert settings.max_retries == 5
    assert settings.cache.uri == "memory:"
    assert settings.nuts_data.name == "NUTS_RG_01M_2021_4326.shp.zip"
    assert settings.geocoders == [GEOCODERS.nominatim]
