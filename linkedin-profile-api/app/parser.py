from __future__ import annotations
from typing import Any

def unwrap(value: Any) -> Any:
    """Turn LinkedIn AttributedText-like values into strings and recursively unwrap containers."""
    if isinstance(value, dict):
        if isinstance(value.get("text"), str) and (
            "attributes" in value or value.get("_type", "").endswith("AttributedText")
        ):
            return value["text"]
        return {k: unwrap(v) for k, v in value.items() if not k.startswith("multiLocale")}
    if isinstance(value, list):
        return [unwrap(v) for v in value]
    return value

def index_included(payload: dict) -> dict[str, dict]:
    return {
        item["entityUrn"]: item
        for item in payload.get("included", [])
        if isinstance(item, dict) and item.get("entityUrn")
    }

def refs(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [x for x in value if isinstance(x, str)]
    if isinstance(value, dict):
        for key in ("*elements", "elements"):
            if key in value:
                return refs(value[key])
    return []

def resolve(index: dict, urn: str | None) -> dict | None:
    return index.get(urn) if urn else None

def first_text(obj: dict | None, *keys: str) -> str | None:
    if not obj:
        return None
    for key in keys:
        value = unwrap(obj.get(key))
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None

def date_string(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    year = value.get("year")
    month = value.get("month")
    if year is None:
        return None
    return f"{year:04d}-{month:02d}" if month else str(year)

def image_url(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    if not isinstance(value, dict):
        return None

    # Common media wrappers.
    for key in ("displayImageUrl", "url", "rootUrl"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
            return candidate

    for key in ("com.linkedin.common.VectorImage", "vectorImage", "vector"):
        vi = value.get(key)
        if isinstance(vi, dict):
            root = vi.get("rootUrl")
            if isinstance(root, str):
                artifacts = vi.get("artifacts") or []
                if artifacts and isinstance(artifacts[-1], dict):
                    return root + (artifacts[-1].get("fileIdentifyingUrlPathSegment") or "")
                return root
    return None

def collect_by_type(index: dict, needles: tuple[str, ...]) -> list[dict]:
    out = []
    for item in index.values():
        typ = str(item.get("$type", "")).lower()
        if any(n.lower() in typ for n in needles):
            out.append(item)
    return out

def walk_collection(index: dict, profile: dict, relation_key: str) -> list[dict]:
    collection_urn = profile.get(relation_key)
    if not collection_urn:
        return []
    collection = resolve(index, collection_urn)
    result = []
    for item_urn in refs(collection):
        item = resolve(index, item_urn)
        if item:
            result.append(item)
    return result

def parse_experience(profile: dict, index: dict) -> list[dict]:
    result = []
    for group in walk_collection(index, profile, "*profilePositionGroups"):
        position_urn = group.get("*profilePositionInPositionGroup")
        collection = resolve(index, position_urn)
        for p_urn in refs(collection):
            p = resolve(index, p_urn)
            if not p:
                continue
            company = resolve(index, p.get("*company"))
            result.append({
                "title": first_text(p, "title"),
                "company": first_text(p, "companyName") or first_text(company, "name"),
                "company_url": company.get("url") if company else None,
                "location": first_text(p, "locationName"),
                "description": first_text(p, "description"),
                "from": date_string((p.get("dateRange") or {}).get("start")),
                "to": date_string((p.get("dateRange") or {}).get("end")) or "present",
            })
    # Fallback for older payloads where the group indirection is absent.
    if not result:
        for p in collect_by_type(index, ("Position",)):
            result.append({
                "title": first_text(p, "title"),
                "company": first_text(p, "companyName"),
                "company_url": None,
                "location": first_text(p, "locationName"),
                "description": first_text(p, "description"),
                "from": date_string((p.get("dateRange") or {}).get("start")),
                "to": date_string((p.get("dateRange") or {}).get("end")) or "present",
            })
    return dedupe_dicts(result)

def parse_education(profile: dict, index: dict) -> list[dict]:
    result = []
    for edu_urn in refs(resolve(index, profile.get("*profileEducations"))):
        edu = resolve(index, edu_urn)
        if not edu:
            continue
        school = resolve(index, edu.get("*school"))
        result.append({
            "school": first_text(edu, "schoolName", "name") or first_text(school, "name"),
            "school_url": school.get("url") if school else None,
            "degree": first_text(edu, "degreeName", "degree"),
            "field_of_study": first_text(edu, "fieldOfStudy"),
            "description": first_text(edu, "description"),
            "from": date_string((edu.get("dateRange") or {}).get("start")),
            "to": date_string((edu.get("dateRange") or {}).get("end")),
        })
    return dedupe_dicts(result)

def parse_skills(profile: dict, index: dict) -> list[dict]:
    # Prefer a profile-linked skill collection when present.
    candidates = []
    for key in ("*profileSkills", "*skills"):
        if profile.get(key):
            candidates.extend(
                resolve(index, urn) or {} for urn in refs(resolve(index, profile[key]))
            )
    if not candidates:
        candidates = collect_by_type(index, ("skill",))
    out = []
    for s in candidates:
        name = first_text(s, "name", "standardizedName", "skillName")
        if name:
            out.append({"name": name, "endorsements": s.get("endorsementCount")})
    return dedupe_dicts(out)

def parse_certifications(profile: dict, index: dict) -> list[dict]:
    candidates = []
    for key in ("*profileCertifications", "*certifications"):
        if profile.get(key):
            candidates.extend(
                resolve(index, urn) or {} for urn in refs(resolve(index, profile[key]))
            )
    if not candidates:
        candidates = collect_by_type(index, ("certification",))
    out = []
    for c in candidates:
        out.append({
            "name": first_text(c, "name", "title"),
            "issuer": first_text(c, "authority", "issuer", "companyName"),
            "issue_date": date_string(c.get("dateRange", {}).get("start")),
            "credential_id": first_text(c, "licenseNumber", "credentialId"),
            "url": c.get("url") if isinstance(c.get("url"), str) else None,
        })
    return dedupe_dicts(out)

def parse_languages(profile: dict, index: dict) -> list[dict]:
    candidates = []
    for key in ("*profileLanguages", "*languages"):
        if profile.get(key):
            candidates.extend(
                resolve(index, urn) or {} for urn in refs(resolve(index, profile[key]))
            )
    if not candidates:
        candidates = collect_by_type(index, ("language",))
    out = []
    for lang in candidates:
        out.append({
            "name": first_text(lang, "name", "languageName"),
            "proficiency": first_text(lang, "proficiency", "proficiencyLevel"),
        })
    return dedupe_dicts(out)

def dedupe_dicts(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for item in items:
        key = tuple(sorted((k, str(v)) for k, v in item.items()))
        if key not in seen and any(v not in (None, "", []) for v in item.values()):
            seen.add(key)
            out.append(item)
    return out

def parse_profile(payload: dict, source_url: str) -> dict:
    index = index_included(payload)
    data = payload.get("data") or {}
    element_refs = data.get("*elements") or data.get("elements") or []
    if not element_refs:
        raise ValueError("No profile reference in LinkedIn response.")
    target_urn = element_refs[0] if isinstance(element_refs[0], str) else None
    profile = resolve(index, target_urn)
    if not profile:
        raise ValueError("Profile entity was not present in LinkedIn response.")

    geo = resolve(index, ((profile.get("geoLocation") or {}).get("geoUrn")))
    picture = (
        profile.get("displayImage")
        or profile.get("profilePicture")
        or profile.get("picture")
        or profile.get("displayPicture")
    )

    first = first_text(profile, "firstName")
    last = first_text(profile, "lastName")
    name = " ".join(x for x in (first, last) if x) or None

    return {
        "public_id": profile.get("publicIdentifier"),
        "profile_urn": target_urn,
        "name": name,
        "first_name": first,
        "last_name": last,
        "headline": first_text(profile, "headline"),
        "location": first_text(profile, "locationName")
                   or first_text(geo, "defaultLocalizedName", "name"),
        "about": first_text(profile, "summary", "about"),
        "profile_image": image_url(picture) or image_url(profile.get("displayPictureUrl")),
        "experience": parse_experience(profile, index),
        "education": parse_education(profile, index),
        "skills": parse_skills(profile, index),
        "certifications": parse_certifications(profile, index),
        "languages": parse_languages(profile, index),
        "raw_available_sections": {
            "included_entities": len(payload.get("included") or []),
            "has_position_groups": bool(profile.get("*profilePositionGroups")),
            "has_educations": bool(profile.get("*profileEducations")),
            "has_skills": bool(profile.get("*profileSkills") or profile.get("*skills")),
            "has_certifications": bool(profile.get("*profileCertifications") or profile.get("*certifications")),
            "has_languages": bool(profile.get("*profileLanguages") or profile.get("*languages")),
        },
        "source": {
            "url": source_url,
            "endpoint": "/voyager/api/identity/dash/profiles",
            "decoration_id": "FullProfileWithEntities-101",
        },
    }
