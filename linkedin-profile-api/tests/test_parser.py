from app.parser import parse_profile

def test_parse_normalized_profile():
    payload = {
        "data": {"*elements": ["urn:li:fsd_profile:p1"]},
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
                "entityUrn": "urn:li:fsd_profile:p1",
                "publicIdentifier": "jane-doe",
                "firstName": {"text": "Jane", "attributes": []},
                "lastName": {"text": "Doe", "attributes": []},
                "headline": {"text": "Engineer", "attributes": []},
                "summary": {"text": "About Jane", "attributes": []},
                "locationName": "Bengaluru",
                "*profilePositionGroups": "urn:li:collection:c1",
                "*profileEducations": "urn:li:collection:e1"
            },
            {
                "entityUrn": "urn:li:collection:c1",
                "*elements": ["urn:li:group:g1"]
            },
            {
                "entityUrn": "urn:li:group:g1",
                "*profilePositionInPositionGroup": "urn:li:collection:p1"
            },
            {
                "entityUrn": "urn:li:collection:p1",
                "*elements": ["urn:li:position:x1"]
            },
            {
                "entityUrn": "urn:li:position:x1",
                "title": {"text": "Software Engineer", "attributes": []},
                "companyName": "Acme",
                "dateRange": {"start": {"year": 2024, "month": 1}}
            },
            {
                "entityUrn": "urn:li:collection:e1",
                "*elements": ["urn:li:education:y1"]
            },
            {
                "entityUrn": "urn:li:education:y1",
                "schoolName": "Example University",
                "degreeName": "B.Tech"
            }
        ]
    }

    out = parse_profile(payload, "https://www.linkedin.com/in/jane-doe")
    assert out["name"] == "Jane Doe"
    assert out["headline"] == "Engineer"
    assert out["experience"][0]["title"] == "Software Engineer"
    assert out["education"][0]["school"] == "Example University"
