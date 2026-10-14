import os

import pytest

import core.keyfinder as K


def test_xor_raw():
    assert K.xor_raw(bytes([1, 2, 3]), bytes([1, 1, 1])) == bytes([0, 3, 2])


def test_parse_manual_key_valid():
    r = K.parse_manual_key("AB" * 32, "wxid_a")
    assert r.passphrase_hex == "ab" * 32 and r.source == "manual"


def test_parse_manual_key_invalid():
    with pytest.raises(ValueError):
        K.parse_manual_key("xyz", "wxid_a")


def test_validate_rejects_bad_key(tmp_path):
    page = os.urandom(K.PAGE)
    (tmp_path / "x.db").write_bytes(page)
    assert K.validate(os.urandom(32), os.urandom(32), tmp_path / "x.db") is None
