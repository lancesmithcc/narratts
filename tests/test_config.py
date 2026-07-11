from service.config import _as_bool, _split_csv


def test_as_bool() -> None:
    assert _as_bool("yes") is True
    assert _as_bool("0") is False


def test_split_csv() -> None:
    assert _split_csv("alpha, beta,,") == ["alpha", "beta"]
