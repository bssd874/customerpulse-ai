from __future__ import annotations

from src.ui import risk_badge, risk_semantic_class


def test_risk_badges_use_danger_warning_and_healthy_semantics() -> None:
    assert risk_semantic_class("HIGH") == "risk-high"
    assert risk_semantic_class("MEDIUM") == "risk-medium"
    assert risk_semantic_class("LOW") == "risk-low"
    assert "risk-high" in risk_badge("HIGH", 88)
    assert "HIGH · 88/100" in risk_badge("HIGH", 88)
