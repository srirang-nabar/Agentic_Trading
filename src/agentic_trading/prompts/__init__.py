"""Versioned prompt templates (Stage 3).

Every instruction template lives here as a file, referenced by SHA-256 hash
in every session log record. Two independently-worded paraphrase templates
per experiment (same economic content) support the robustness requirement
on primary claims. Templates follow the contamination protocol: designs are
never named, asset/currency units are relabeled.
"""
