from dotdoctor.infrastructure.checks.utils import is_version_at_least, parse_version


def test_parse_version_with_patch() -> None:
    assert parse_version("Python 3.11.9") == (3, 11, 9)


def test_parse_version_without_patch() -> None:
    assert parse_version("git version 2.43") == (2, 43, 0)


def test_is_version_at_least() -> None:
    assert is_version_at_least((3, 11, 0), (3, 10, 9))
    assert not is_version_at_least((3, 10, 0), (3, 11, 0))
