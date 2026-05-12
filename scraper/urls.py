"""
Backward-compatibility shim.

Logic has moved to domains/automotive/url_builder.py.
Importing from this module still works for existing callers.
"""

from domains.automotive.url_builder import build_search_url  # noqa: F401
