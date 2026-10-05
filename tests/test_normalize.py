from wadi_scraper.config import NormalizeConfig
from wadi_scraper.normalize import normalize_url


def test_normalize_host_and_fragment():
    cfg = NormalizeConfig(scheme="https", lowercase_host=True, strip_fragment=True)
    out = normalize_url("HTTPS://WWW.Reebok.com/pages/x#section", cfg)
    assert out == "https://www.reebok.com/pages/x"
