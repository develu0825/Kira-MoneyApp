"""
Kira 데이터 암호화 (AES-256-GCM + PBKDF2-SHA256).

공개 레포에 올려도 안전하도록 거래 데이터를 암호화한다.
브라우저(Web Crypto)와 포맷을 맞춰, 폰 PWA에서 같은 암호로 복호화할 수 있다.

출력 포맷(JSON):
  {"v":1,"iter":200000,"salt":b64,"iv":b64,"ct":b64}
  - ct = AES-GCM(ciphertext + 16-byte tag)  ← Web Crypto와 호환
"""

import os
import json
import base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITERATIONS = 200_000


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _ub64(s: str) -> bytes:
    return base64.b64decode(s)


def _derive_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt(plaintext: str, passphrase: str) -> dict:
    """문자열을 암호화해 Web Crypto 호환 blob(dict)로 반환."""
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = _derive_key(passphrase, salt, ITERATIONS)
    ct = AESGCM(key).encrypt(iv, plaintext.encode("utf-8"), None)  # ct에 16-byte tag 포함
    return {"v": 1, "iter": ITERATIONS, "salt": _b64(salt), "iv": _b64(iv), "ct": _b64(ct)}


def decrypt(blob: dict, passphrase: str) -> str:
    """encrypt()가 만든 blob을 복호화 (검증/디버깅용)."""
    salt = _ub64(blob["salt"])
    iv = _ub64(blob["iv"])
    ct = _ub64(blob["ct"])
    key = _derive_key(passphrase, salt, blob.get("iter", ITERATIONS))
    pt = AESGCM(key).decrypt(iv, ct, None)
    return pt.decode("utf-8")


def encrypt_to_file(data: dict, passphrase: str, path: str) -> None:
    blob = encrypt(json.dumps(data, ensure_ascii=False, separators=(",", ":")), passphrase)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(blob, f)


if __name__ == "__main__":
    # self-test
    blob = encrypt('{"hello":"키라"}', "test-pass")
    assert decrypt(blob, "test-pass") == '{"hello":"키라"}'
    print("kira_crypto self-test OK")
