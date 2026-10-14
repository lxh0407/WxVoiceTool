import os

from Crypto.Cipher import AES
from Crypto.Hash import SHA512
from Crypto.Protocol.KDF import PBKDF2

import core.dbdecrypt as D


def _make_fake_page(passphrase, salt):
    enc = D.make_enc_key(passphrase, salt)
    plain = b"SQLite format 3\x00" + os.urandom(D.PAGE - 16 - D.RESERVE) + b"\x50" * D.RESERVE
    iv = os.urandom(16)
    ct = AES.new(enc, AES.MODE_CBC, iv).encrypt(plain[16:D.PAGE - D.RESERVE])
    return salt + ct + iv + b"\x00" * (D.RESERVE - 16)


def test_decrypt_page1_recovers_header():
    salt = os.urandom(16)
    pp = os.urandom(32)
    page = _make_fake_page(pp, salt)
    out = D.decrypt_page1(page, D.make_enc_key(pp, salt))
    assert out[:16] == b"SQLite format 3\x00"


def test_make_enc_key_uses_pbkdf2_sha512():
    assert D.make_enc_key(b"a" * 32, b"s" * 16) == PBKDF2(
        b"a" * 32, b"s" * 16, dkLen=32, count=256000, hmac_hash_module=SHA512
    )
