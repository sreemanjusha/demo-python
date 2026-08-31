from urllib.parse import urlparse, unquote

def extract_public_id(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = parsed.netloc.lower().split(":")[0]
    if host not in {"linkedin.com", "www.linkedin.com"}:
        return None

    parts = [unquote(p) for p in parsed.path.split("/") if p]
    if len(parts) < 2 or parts[0].lower() != "in":
        return None

    public_id = parts[1].strip()
    if not public_id or public_id.startswith("?"):
        return None
    # LinkedIn public identifiers are URL-safe slugs. Keep the validator permissive
    # because newer identifiers can contain punctuation.
    if len(public_id) > 200:
        return None
    return public_id
