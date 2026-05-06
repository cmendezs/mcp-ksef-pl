"""Payload encryption for KSeF API v2.

KSeF v2 requires every invoice submitted via an online or batch session to be
encrypted before transmission:

  1. A fresh 256-bit AES key and 128-bit IV are generated per session.
  2. The AES key is wrapped with the Ministry of Finance RSA public key using
     OAEP padding (SHA-256 hash, SHA-256 MGF1).
  3. Each invoice body is encrypted with AES-256-CBC + PKCS7 padding.
  4. SHA-256 hashes of both the plaintext and ciphertext are sent alongside the
     encrypted content so KSeF can verify integrity after decryption.

The MF public key is fetched from GET /security/public-key-certificates and
filtered to the certificate with usage "SymmetricKeyEncryption".  The endpoint
returns DER-encoded X.509 certificates encoded in Base64; this module loads the
RSA public key from the certificate using the `cryptography` library.

Reference: https://github.com/CIRFMF/ksef-docs/blob/main/sesja-interaktywna.md
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


def load_mf_public_key(certificate_b64: str) -> RSAPublicKey:
    """Load the MF RSA public key from a Base64-encoded DER X.509 certificate.

    Args:
        certificate_b64: Base64-encoded DER certificate from the
                         GET /security/public-key-certificates response,
                         filtered to usage == "SymmetricKeyEncryption".

    Returns:
        RSAPublicKey ready for OAEP encryption.

    Raises:
        ValueError: If the certificate does not contain an RSA public key.
    """
    cert_der = base64.b64decode(certificate_b64)
    cert = x509.load_der_x509_certificate(cert_der)
    public_key = cert.public_key()
    if not isinstance(public_key, RSAPublicKey):
        raise ValueError(
            f"MF certificate contains a {type(public_key).__name__} key; "
            "expected RSAPublicKey for SymmetricKeyEncryption."
        )
    return public_key


class InvoiceEnvelope:
    """One-shot AES-256-CBC encryption envelope for a single KSeF v2 session.

    Create one instance per online session.  The same AES key and IV are used
    for every invoice sent within that session.

    Usage:
        envelope = InvoiceEnvelope(mf_public_key)
        # Pass these when opening the session:
        session_payload = {
            "encryption": {
                "encryptedSymmetricKey": envelope.encrypted_symmetric_key,
                "initializationVector": envelope.initialization_vector,
            },
            ...
        }
        # Then for each invoice:
        send_payload = envelope.build_send_payload(xml_content)
    """

    def __init__(self, mf_public_key: RSAPublicKey) -> None:
        self._aes_key: bytes = os.urandom(32)  # 256-bit
        self._iv: bytes = os.urandom(16)        # 128-bit CBC IV

        encrypted_key = mf_public_key.encrypt(
            self._aes_key,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        self._encrypted_symmetric_key: str = base64.b64encode(encrypted_key).decode()
        self._initialization_vector: str = base64.b64encode(self._iv).decode()

    @property
    def encrypted_symmetric_key(self) -> str:
        """Base64-encoded AES key wrapped with MF RSA public key (OAEP + SHA-256)."""
        return self._encrypted_symmetric_key

    @property
    def initialization_vector(self) -> str:
        """Base64-encoded 16-byte AES-CBC IV."""
        return self._initialization_vector

    def build_send_payload(self, xml_content: str) -> dict[str, object]:
        """Encrypt *xml_content* and return the SendInvoiceRequest body dict.

        Fields produced:
          invoiceHash              SHA-256 of original XML bytes (Base64, 44 chars)
          invoiceSize              Byte length of original XML (UTF-8 encoded)
          encryptedInvoiceHash     SHA-256 of encrypted bytes (Base64, 44 chars)
          encryptedInvoiceSize     Byte length of encrypted payload
          encryptedInvoiceContent  AES-256-CBC ciphertext (Base64)

        Args:
            xml_content: FA(3) invoice XML string (UTF-8).

        Returns:
            Dict ready to be serialised as the request body for
            POST /sessions/online/{referenceNumber}/invoices.
        """
        xml_bytes = xml_content.encode("utf-8")

        invoice_hash = base64.b64encode(
            hashlib.sha256(xml_bytes).digest()
        ).decode()

        padder = PKCS7(algorithms.AES.block_size).padder()
        padded = padder.update(xml_bytes) + padder.finalize()

        cipher = Cipher(algorithms.AES(self._aes_key), modes.CBC(self._iv))
        encryptor = cipher.encryptor()
        encrypted: bytes = encryptor.update(padded) + encryptor.finalize()

        encrypted_hash = base64.b64encode(
            hashlib.sha256(encrypted).digest()
        ).decode()

        return {
            "invoiceHash": invoice_hash,
            "invoiceSize": len(xml_bytes),
            "encryptedInvoiceHash": encrypted_hash,
            "encryptedInvoiceSize": len(encrypted),
            "encryptedInvoiceContent": base64.b64encode(encrypted).decode(),
        }
