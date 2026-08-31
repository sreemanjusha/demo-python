from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, HttpUrl
from app.linkedin import LinkedInClient, LinkedInAuthError, LinkedInRateLimitError, LinkedInUpstreamError
from app.parser import parse_profile
from app.url_parser import extract_public_id

app = FastAPI(
    title="LinkedIn Profile API",
    version="1.0.0",
    description="Browserless, reverse-engineered LinkedIn Voyager profile extraction API.",
)

class ProfileRequest(BaseModel):
    url: HttpUrl

class ProfileResponse(BaseModel):
    source_url: str
    profile: dict

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/v1/profile", response_model=ProfileResponse)
def profile(req: ProfileRequest, x_api_key: str | None = Header(default=None)):
    # Optional API protection for public deployments.
    import os
    expected = os.getenv("API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")

    public_id = extract_public_id(str(req.url))
    if not public_id:
        raise HTTPException(
            status_code=422,
            detail="Only LinkedIn profile URLs in the form https://www.linkedin.com/in/<public-id> are supported.",
        )

    try:
        client = LinkedInClient.from_env()
        raw = client.fetch_profile(public_id)
        parsed = parse_profile(raw, source_url=str(req.url))
        return {"source_url": str(req.url), "profile": parsed}
    except LinkedInAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except LinkedInRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except LinkedInUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Unexpected LinkedIn response: {exc}")
