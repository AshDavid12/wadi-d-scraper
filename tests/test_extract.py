from wadi_scraper.extract import extract_from_html, normalize_field


def test_extract_title_and_meta():
    html = """
    <html><head>
    <title>Shoes on Sale | Reebok</title>
    <meta name="description" content="Save on Classics &amp; runners." />
    <link rel="canonical" href="https://www.reebok.com/collections/sale" />
    </head><body><h1>Sale</h1></body></html>
    """
    fields = extract_from_html(
        "https://www.reebok.com/collections/sale",
        "https://www.reebok.com/collections/sale",
        200,
        html,
    )
    assert fields.title == "Shoes on Sale | Reebok"
    assert fields.meta_description == "Save on Classics & runners."
    assert fields.h1s == ["Sale"]
    assert fields.canonical_url.endswith("/collections/sale")


def test_normalize_field_unescapes():
    assert normalize_field("foo &amp; bar") == "foo & bar"


def test_title_change_detection_pair():
    html_before = "<html><head><title>Old Title</title></head><body></body></html>"
    html_after = "<html><head><title>New Title</title></head><body></body></html>"
    from wadi_scraper.seo_diff import diff_page_fields

    before = extract_from_html("https://x/", "https://x/", 200, html_before)
    after = extract_from_html("https://x/", "https://x/", 200, html_after)
    changes = diff_page_fields(before, after)
    assert len(changes) == 1
    assert changes[0].field == "title"
    assert changes[0].before == "Old Title"
    assert changes[0].after == "New Title"
