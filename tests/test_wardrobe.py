from datetime import datetime

import pytest

from jarvis import wardrobe
from jarvis.models import WardrobeItem
from jarvis.wardrobe import _heuristic_gaps, find_wardrobe_gaps


def _item(**overrides) -> WardrobeItem:
    base = dict(
        item_id="abc123",
        image_path="images/abc123.jpg",
        category="top",
        subtype="t-shirt",
        primary_color="black",
        secondary_colors=[],
        warmth=2,
        formality="casual",
        rain_ok=False,
        style_tags=["minimalist"],
        description="A plain black tee.",
        added_at=datetime(2026, 9, 1, 8, 0),
    )
    base.update(overrides)
    return WardrobeItem(**base)


def test_empty_wardrobe_flags_missing_categories():
    gaps = _heuristic_gaps([])
    assert any("tops" in g for g in gaps)
    assert any("outerwear" in g for g in gaps)


def test_full_wardrobe_has_fewer_gaps():
    items = [
        _item(item_id="1", category="top"),
        _item(item_id="2", category="bottom", subtype="jeans"),
        _item(item_id="3", category="outerwear", subtype="winter coat", warmth=5),
        _item(item_id="4", category="shoes", subtype="sneakers"),
        _item(item_id="5", category="outerwear", subtype="rain shell", rain_ok=True),
        _item(item_id="6", category="top", subtype="dress shirt", formality="smart_casual"),
        _item(item_id="7", category="top", subtype="gym shirt", formality="athletic"),
    ]
    gaps = _heuristic_gaps(items)
    assert gaps == []


def test_find_wardrobe_gaps_without_api_key_uses_heuristic():
    result = find_wardrobe_gaps([], None, "", api_key=None, model="unused")
    assert "empty" in result[0].lower()


def test_wardrobe_round_trip_via_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(wardrobe, "WARDROBE_DIR", tmp_path)
    monkeypatch.setattr(wardrobe, "IMAGES_DIR", tmp_path / "images")
    monkeypatch.setattr(wardrobe, "ITEMS_PATH", tmp_path / "items.json")

    assert wardrobe.load_wardrobe() == []

    items = [_item(item_id="1"), _item(item_id="2", category="shoes", subtype="boots")]
    wardrobe.save_wardrobe(items)

    loaded = wardrobe.load_wardrobe()
    assert [it.item_id for it in loaded] == ["1", "2"]
    assert loaded[0].subtype == "t-shirt"
    assert loaded[1].category == "shoes"


def test_remove_item(tmp_path, monkeypatch):
    monkeypatch.setattr(wardrobe, "WARDROBE_DIR", tmp_path)
    monkeypatch.setattr(wardrobe, "IMAGES_DIR", tmp_path / "images")
    monkeypatch.setattr(wardrobe, "ITEMS_PATH", tmp_path / "items.json")

    wardrobe.save_wardrobe([_item(item_id="1"), _item(item_id="2")])

    assert wardrobe.remove_item("1") is True
    assert [it.item_id for it in wardrobe.load_wardrobe()] == ["2"]
    assert wardrobe.remove_item("does-not-exist") is False


def test_build_style_profile_requires_items():
    with pytest.raises(ValueError):
        wardrobe.build_style_profile([], "", api_key="fake-key", model="unused")


def test_build_style_profile_requires_api_key():
    with pytest.raises(RuntimeError):
        wardrobe.build_style_profile([_item()], "", api_key=None, model="unused")
