"""
Name filter helpers: multi-word AND/OR include terms, exclude terms, extensions.
Used by FileSortFilterProxy after entry kind filtering.
"""

from __future__ import annotations

import fnmatch
import os
import re
from typing import Dict, List, Optional, Tuple


def parse_filter_terms(text: str) -> List[str]:
    """Split user text into separate search terms (whitespace or comma)."""
    if not text or not str(text).strip():
        return []
    return [part for part in re.split(r"[\s,]+", str(text).strip()) if part]


def parse_extensions(text: str) -> List[str]:
    """
    Parse extension list from user text.
    Accepts: txt, pdf | .txt;.pdf | *.docx
    Returns normalized lowercase extensions with leading dot.
    """
    if not text or not str(text).strip():
        return []
    out: List[str] = []
    for raw in re.split(r"[\s,;]+", str(text).strip()):
        token = raw.strip().lower()
        if not token:
            continue
        if token.startswith("*."):
            token = token[2:]
        token = token.lstrip(".")
        if not token:
            continue
        out.append("." + token)
    return out


def _compile_regex(pattern: str) -> Tuple[Optional[re.Pattern], bool]:
    try:
        return re.compile(pattern, re.IGNORECASE | re.UNICODE), False
    except re.error:
        return None, True


def match_single_term(name: str, term: str, mode: str, regex_obj=None) -> bool:
    """Return True if one include/exclude term matches the entry name."""
    if not term:
        return False
    if mode == "contains":
        return term.lower() in name.lower()
    if mode == "wildcard":
        return fnmatch.fnmatch(name.lower(), term.lower())
    if mode == "regex":
        if regex_obj is None:
            regex_obj, invalid = _compile_regex(term)
            if invalid or regex_obj is None:
                return False
        return regex_obj.search(name) is not None
    return term.lower() in name.lower()


def match_include_terms(
    name: str,
    terms: List[str],
    mode: str,
    combine_and: bool,
    regex_cache: Optional[Dict[str, Tuple[Optional[re.Pattern], bool]]] = None,
) -> bool:
    """Match filename against one or more include terms with AND/OR."""
    if not terms:
        return True
    if regex_cache is None:
        regex_cache = {}

    results: List[bool] = []
    for term in terms:
        regex_obj = None
        if mode == "regex":
            if term not in regex_cache:
                regex_cache[term] = _compile_regex(term)
            regex_obj, invalid = regex_cache[term]
            if invalid:
                results.append(False)
                continue
        results.append(match_single_term(name, term, mode, regex_obj))

    if combine_and:
        return all(results)
    return any(results)


def match_exclude_terms(
    name: str,
    terms: List[str],
    mode: str,
    regex_cache: Optional[Dict[str, Tuple[Optional[re.Pattern], bool]]] = None,
) -> bool:
    """Return True if the name should be excluded (any exclude term matches)."""
    if not terms:
        return False
    if regex_cache is None:
        regex_cache = {}

    for term in terms:
        regex_obj = None
        if mode == "regex":
            if term not in regex_cache:
                regex_cache[term] = _compile_regex(term)
            regex_obj, invalid = regex_cache[term]
            if invalid:
                continue
        if match_single_term(name, term, mode, regex_obj):
            return True
    return False


def match_extension(filename: str, extensions: List[str]) -> bool:
    """Return True if file extension is in the allowed list (or list is empty)."""
    if not extensions:
        return True
    ext = os.path.splitext(filename)[1].lower()
    return ext in extensions
