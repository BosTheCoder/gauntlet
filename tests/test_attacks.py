import pytest

from gauntlet.attacks import BUILTIN_FAMILIES, AttackError, load_corpus, select


def test_builtin_corpus_covers_the_documented_families():
    corpus = load_corpus()
    assert {a.family for a in corpus} == set(BUILTIN_FAMILIES)


def test_every_builtin_attack_is_complete_and_uniquely_identified():
    corpus = load_corpus()
    ids = [a.id for a in corpus]
    assert len(set(ids)) == len(ids)
    assert all(a.payload.strip() and a.note.strip() and a.remediation.strip() for a in corpus)


def test_select_orders_by_the_requested_families_then_corpus_order():
    corpus = load_corpus()
    picked = select(corpus, ["tool_hijack", "encoding"])
    families = [a.family for a in picked]
    assert families == sorted(families, key=lambda f: ["tool_hijack", "encoding"].index(f))
    assert set(families) == {"tool_hijack", "encoding"}


def test_select_rejects_a_family_that_is_not_in_the_corpus():
    with pytest.raises(AttackError):
        select(load_corpus(), ["not_a_family"])


def test_a_custom_directory_adds_attacks_to_the_corpus(tmp_path):
    (tmp_path / "house_style.yaml").write_text(
        """
family: house_style
remediation: fix it
attacks:
  - id: hs-one
    payload: "do the thing"
    note: "a note"
"""
    )
    corpus = load_corpus(tmp_path)
    ids = [a.id for a in corpus]
    assert "hs-one" in ids
    assert len(ids) == len(load_corpus()) + 1


def test_a_custom_family_carries_its_remediation(tmp_path):
    (tmp_path / "house_style.yaml").write_text(
        """
family: house_style
remediation: "scope the tool"
attacks:
  - id: hs-one
    payload: "do the thing"
    note: "a note"
"""
    )
    attack = next(a for a in load_corpus(tmp_path) if a.id == "hs-one")
    assert attack.remediation == "scope the tool"


def test_a_malformed_attack_file_is_rejected(tmp_path):
    (tmp_path / "broken.yaml").write_text("family: x\nattacks: [{id: a}]\n")
    with pytest.raises(AttackError):
        load_corpus(tmp_path)
