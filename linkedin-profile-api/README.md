# LinkedIn Profile API — Browserless Voyager

A small FastAPI service that accepts a LinkedIn `/in/<public-id>` URL and returns a normalized JSON profile.

> **Challenge alignment:** the hiring brief asks for a public HTTPS API, a LinkedIn profile URL input, structured profile data, a public source repository, documentation, no secrets in Git, and a browserless solution that directly calls LinkedIn endpoints. The implementation here uses raw HTTP requests to LinkedIn's internal Voyager endpoint; no Selenium, Playwright, Puppeteer, or browser automation is in the runtime.

## Architecture

```text
Client
  |
  | POST /v1/profile
  v
FastAPI
  |
  | validate + extract /in/<public-id>
  v
LinkedInClient
  |
  | HTTPS GET /voyager/api/identity/dash/profiles
  | cookies: li_at + JSESSIONID
  | csrf-token: JSESSIONID
  v
LinkedIn Voyager
  |
  v
normalized JSON {data, included}
  |
  v
Graph resolver / parser
  |
  v
stable JSON schema
```

## Why this endpoint

The older `GET /voyager/api/identity/profiles/{id}/profileView` path is no longer a reliable implementation target. Current reverse-engineering references report it returning 410 and identify `/voyager/api/identity/dash/profiles` with the `FullProfileWithEntities-101` decoration as the profile endpoint. The response is a normalized graph: `data.*elements` contains URN references and `included[]` contains entities. The parser therefore resolves relationships by URN rather than globally scraping every `Position` record.

The exact private endpoint, decoration ID, cookie/header contract, and response fields can change without notice. Keep the decoration ID in an environment variable so a future LinkedIn deployment can be updated without changing the API contract.

## Authentication

This service intentionally does **not** automate a username/password login.

Set:

- `LINKEDIN_LI_AT`: your own logged-in LinkedIn session cookie
- `LINKEDIN_JSESSIONID`: your own JSESSIONID cookie

Do not put either value in GitHub, Docker images, source code, logs, screenshots, or README examples.

## Local setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env  # Windows
# cp .env.example .env # macOS/Linux

uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Profile request:

```bash
curl -X POST http://localhost:8000/v1/profile \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d "{\"url\":\"https://www.linkedin.com/in/example\"}"
```

If `API_KEY` is unset, the `X-API-Key` header is not required.

## API

### `GET /health`

Returns:

```json
{"status":"ok"}
```

### `POST /v1/profile`

Request:

```json
{
  "url": "https://www.linkedin.com/in/example"
}
```

Response shape:

```json
{
  "source_url": "https://www.linkedin.com/in/example",
  "profile": {
    "public_id": "example",
    "profile_urn": "urn:li:fsd_profile:...",
    "name": "Jane Doe",
    "first_name": "Jane",
    "last_name": "Doe",
    "headline": "Software Engineer",
    "location": "Bengaluru",
    "about": "...",
    "profile_image": "https://...",
    "experience": [],
    "education": [],
    "skills": [],
    "certifications": [],
    "languages": [],
    "raw_available_sections": {},
    "source": {}
  }
}
```

Fields are nullable/empty when LinkedIn does not expose them for the session/profile.

## Deployment

The container listens on `$PORT`, so it is suitable for Render, Railway, Fly.io, or any HTTPS container host.

Example:

```bash
docker build -t linkedin-profile-api .
docker run --rm -p 8000:8000 \
  -e LINKEDIN_LI_AT="$LINKEDIN_LI_AT" \
  -e LINKEDIN_JSESSIONID="$LINKEDIN_JSESSIONID" \
  -e API_KEY="$API_KEY" \
  linkedin-profile-api
```

For a public HTTPS deployment:

1. Create a private service/environment on your chosen host.
2. Connect the public GitHub repository.
3. Deploy from the included `Dockerfile`.
4. Add `LINKEDIN_LI_AT`, `LINKEDIN_JSESSIONID`, and a random `API_KEY` as platform secrets.
5. Enable the provider's HTTPS URL.
6. Test `GET /health`.
7. Test `POST /v1/profile` with `X-API-Key`.

Never print environment variables in build logs.

## Reverse-engineering notes

- Voyager uses a normalized JSON graph: references in `data`, entities in `included`.
- The requested profile is resolved from `data.*elements[0]`, not by taking the first `Profile` entity in `included`.
- Experience is resolved through `Profile.*profilePositionGroups -> CollectionResponse.*elements -> PositionGroup.*profilePositionInPositionGroup -> CollectionResponse.*elements -> Position`.
- Attributed text can arrive as `{text, attributes}` and is unwrapped.
- Modern location data can require resolving `geoLocation.geoUrn` into a `Geo` entity.
- The old `profileView` endpoint should not be used as the primary path.
- Query/decorations are configuration because LinkedIn can change private contracts.

## Known limitations

1. This uses undocumented LinkedIn internal endpoints. It is not the official LinkedIn API.
2. LinkedIn can change query decorations, response shapes, authentication requirements, rate limits, or block a session at any time.
3. A profile's visibility/privacy settings determine what the session can see.
4. Certifications, languages, and skills are parsed when the profile response exposes linked entities/collections; they are not fabricated when absent.
5. The profile image URL may be a media-proxy/vector-image URL and can expire or change.
6. A single session is used by this minimal implementation. Production scaling should use strict request quotas, observability, secret rotation, and a queue rather than high-concurrency bursts.
7. The service does not attempt to bypass CAPTCHA, checkpoints, MFA, rate limits, or other access controls.
8. Do not log raw LinkedIn responses: they can contain personal data and session-sensitive material.

## Security checklist

- [x] Secrets are environment variables.
- [x] `.env` is ignored.
- [x] Optional API key for public endpoint.
- [x] No credentials in source.
- [x] No raw upstream payload logging.
- [x] No browser automation in the API.
- [x] No username/password authentication flow.
- [x] Explicit 401/403/429 handling.
- [ ] Add platform-level secret management and request-rate limits before production.

## What to submit

- Public GitHub repository containing this source.
- README (this file).
- Public HTTPS base URL.
- Example request/response.
- A short note explaining that the implementation directly calls Voyager and does not use a browser.

Before submitting, replace `example` in documentation/examples with a test profile you are authorized to access and verify the deployed URL.
