import hashlib
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_key(password):
    return hashlib.sha256(password.encode()).digest()


def encrypt_message(message, key):
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, message.encode(), None)
    return nonce + ciphertext


def decrypt_message(data, key):
    nonce = data[:12]
    ciphertext = data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


def encrypt_bytes(data, key):
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    return nonce + aesgcm.encrypt(nonce, data, None)


def decrypt_bytes(data, key):
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(data[:12], data[12:], None)
