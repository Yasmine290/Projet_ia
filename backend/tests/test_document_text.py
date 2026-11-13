import pytest

from app.services.documents import split_text


def test_split_text_prefers_sentence_boundaries_and_limits_size() -> None:
    """Les phrases complètes sont privilégiées sans dépasser la taille fixée."""
    chunks = split_text("Première phrase.   Deuxième phrase !\nTroisième phrase.", 22)
    assert chunks == ["Première phrase.", "Deuxième phrase !", "Troisième phrase."]
    assert all(len(chunk) <= 22 for chunk in chunks)


def test_split_text_handles_long_words_and_empty_text() -> None:
    """Un mot plus long que la limite est découpé sans perte ni boucle infinie."""
    assert split_text("abcdefghijk", 4) == ["abcd", "efgh", "ijk"]
    assert split_text(" \n\t ", 4) == []
    with pytest.raises(ValueError):
        split_text("texte", 0)
