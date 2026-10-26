"""Register and resolve category profiles.

Future categories: import the profile module and append to ``_PROFILES``.
"""

from __future__ import annotations

from shopping_agent.profiles.base import CategoryProfile
from shopping_agent.profiles.headphones import PROFILE as HEADPHONES_PROFILE
from shopping_agent.profiles.laptops import PROFILE as LAPTOP_PROFILE

# Registration order is match priority when multiple profiles could match.
_PROFILES: tuple[CategoryProfile, ...] = (
    LAPTOP_PROFILE,
    HEADPHONES_PROFILE,
)

_BY_ID: dict[str, CategoryProfile] = {profile.id: profile for profile in _PROFILES}


def registered_profiles() -> tuple[CategoryProfile, ...]:
    return _PROFILES


def supported_category_ids() -> tuple[str, ...]:
    return tuple(profile.id for profile in _PROFILES)


def get_profile(category_id: str) -> CategoryProfile:
    try:
        return _BY_ID[category_id.casefold().strip()]
    except KeyError as exc:
        supported = ", ".join(supported_category_ids())
        raise KeyError(
            f"Unsupported category {category_id!r}. Supported profiles: {supported}."
        ) from exc


def match_profile(text: str) -> CategoryProfile | None:
    """Return the first registered profile whose category terms match *text*."""
    if not text or not text.strip():
        return None
    for profile in _PROFILES:
        if profile.matches_category(text):
            return profile
    return None
