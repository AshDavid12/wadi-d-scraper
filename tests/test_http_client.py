from wadi_scraper.http_client import looks_like_bot_wall

HOKA_403 = b"""<html><body><p>Please enable JS and disable any ad blocker</p>
<script>host':'geo.captcha-delivery.com'</script></html>"""


def test_hoka_captcha_page_detected_as_bot_wall():
    assert looks_like_bot_wall(403, HOKA_403)
