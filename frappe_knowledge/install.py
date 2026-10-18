"""Schema setup needed on both fresh installs and upgraded sites."""

from frappe_knowledge.patches.v0_4 import add_chunk_file_lookup, add_source_search_index


def after_install():
	"""Fresh installs skip patches, so create their source-search indexes here."""
	add_source_search_index.execute()
	add_chunk_file_lookup.execute()
