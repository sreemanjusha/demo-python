from app.url_parser import extract_public_id

def test_extract_profile_id():
    assert extract_public_id("https://www.linkedin.com/in/jane-doe-123/?trk=x") == "jane-doe-123"

def test_reject_non_profile():
    assert extract_public_id("https://www.linkedin.com/company/acme/") is None
    assert extract_public_id("https://example.com/in/jane") is None
