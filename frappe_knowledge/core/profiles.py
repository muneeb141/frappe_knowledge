"""Knowledge compatibility rules, independent of the Frappe host runtime.

Adding a source app is a registry change. Other knowledge profiles remain disabled
until they have their own rules and verification suite.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceApp:
	app: str
	repository: str
	version_major: str | None = None


@dataclass(frozen=True)
class CompatibilityProfile:
	name: str
	framework_major: str
	apps: tuple[SourceApp, ...]
	active: bool = True


FRAPPE_V16 = CompatibilityProfile(
	name="frappe-v16",
	framework_major="16",
	apps=(
		SourceApp("frappe", "frappe/frappe", "16"),
		SourceApp("erpnext", "frappe/erpnext", "16"),
		SourceApp("hrms", "frappe/hrms", "16"),
	),
)
PROFILES = {FRAPPE_V16.name: FRAPPE_V16}


def get_profile(name: str, *, registry=PROFILES) -> CompatibilityProfile:
	profile = registry.get(name)
	if not profile or not profile.active:
		raise ValueError("Knowledge profile is unavailable")
	return profile


def validate_sources(name: str, sources: list[dict], *, registry=PROFILES) -> None:
	"""Check declared source versions against the selected knowledge profile.

	A partial snapshot may contain a subset of the profile's apps. This check
	does not establish that the declared revisions match a real checkout.
	"""
	profile = get_profile(name, registry=registry)
	allowed = {app.app: app for app in profile.apps}
	seen = set()
	if not sources:
		raise ValueError("At least one source is required")
	for source in sources:
		app = source.get("app")
		rule = allowed.get(app)
		if not rule or app in seen:
			raise ValueError("Source app is unavailable or duplicated for this profile")
		seen.add(app)
		if source.get("repository") != rule.repository:
			raise ValueError("Source repository does not match the profile registry")
		version = source.get("version")
		if not isinstance(version, str) or not re.fullmatch(r"[0-9]+(?:[.][0-9A-Za-z-]+)*", version):
			raise ValueError("A source app version is required")
		if rule.version_major and version.split(".", 1)[0] != rule.version_major:
			raise ValueError("Source app version is incompatible with the profile")
