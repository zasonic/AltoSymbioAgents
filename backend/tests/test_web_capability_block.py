"""tests/test_web_capability_block.py — MemoryRecall web-capability prompt block.

The block must appear only for a research agent when web research is enabled,
and be byte-absent otherwise (so a flag-off turn is unchanged).
"""

from __future__ import annotations

import json

import pytest

from services.memory_recall import MemoryRecall


class _Settings:
    def __init__(self, **kw):
        self._d = kw
    def get(self, key, default=None):
        return self._d.get(key, default)


def _recall(**flags):
    # memory + mcp_registry are unused by _web_capability_block.
    return MemoryRecall(memory=None, settings=_Settings(**flags), mcp_registry=None)


def _agent(*skill_names):
    return {"skills": json.dumps([{"name": n} for n in skill_names])}


def test_block_present_for_research_agent_when_enabled():
    block = _recall(web_research_enabled=True)._web_capability_block(_agent("researcher"))
    assert "## Web research" in block


def test_block_absent_when_flag_off():
    assert _recall(web_research_enabled=False)._web_capability_block(_agent("researcher")) == ""


def test_block_absent_for_non_research_agent():
    block = _recall(web_research_enabled=True)._web_capability_block(_agent("writer"))
    assert block == ""


def test_block_absent_without_agent():
    assert _recall(web_research_enabled=True)._web_capability_block(None) == ""


@pytest.mark.parametrize("skill", ["researcher", "web-search", "Deep Research"])
def test_research_like_skills_match(skill):
    assert _recall(web_research_enabled=True)._web_capability_block(_agent(skill))
