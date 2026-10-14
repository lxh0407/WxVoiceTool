from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Hash import SHA512
from Crypto.Protocol.KDF import PBKDF2

PAGE = 4096
RESERVE = 80
IV_SZ = 16
KEY_SZ = 32
KDF_ITER = 256000


def make_enc_key(passphrase: bytes, salt: bytes) -> bytes:
    return PBKDF2(passphrase, salt, dkLen=KEY_SZ, count=KDF_ITER, hmac_hash_module=SHA512)


def decrypt_page1(page: bytes, enc_key: bytes) -> bytes:
    iv = page[PAGE - RESERVE:PAGE - RESERVE + IV_SZ]
    ct = page[16:PAGE - RESERVE]
    pt = AES.new(enc_key, AES.MODE_CBC, iv).decrypt(ct)
    return b"SQLite format 3\x00" + pt + b"\x00" * RESERVE


def decrypt_db(src, dst, passphrase: bytes) -> None:
    data = Path(src).read_bytes()
    salt = data[:16]
    enc = make_enc_key(passphrase, salt)
    n = len(data)
    out = bytearray()
    off = 0
    idx = 0
    while off < n:
        page = data[off:off + PAGE]
        if idx == 0:
            out += decrypt_page1(page, enc)
        else:
            iv = page[PAGE - RESERVE:PAGE - RESERVE + IV_SZ]
            ct = page[0:PAGE - RESERVE]
            cut = (len(ct) // 16) * 16
            if cut == 0:
                break
            out += AES.new(enc, AES.MODE_CBC, iv).decrypt(ct[:cut])
            if len(page) == PAGE:
                out += b"\x00" * RESERVE
        off += PAGE
        idx += 1
    Path(dst).write_bytes(bytes(out))
