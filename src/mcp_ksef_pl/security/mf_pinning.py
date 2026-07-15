"""SPKI SHA-256 fingerprint pinning for the KSeF Ministry of Finance encryption cert (PL-3.6).

Cross-reference: the 2026-05 security audit (P2) flagged that `load_mf_public_key`
trusted the certificate returned by GET /security/public-key-certificates without
pinning or chain validation. This module adds an opt-in SPKI (SubjectPublicKeyInfo)
SHA-256 fingerprint allowlist, chosen over full chain validation because it is
simpler to audit, does not require bundling a Ministry of Finance root CA, and
rotates cleanly by adding a new pin entry alongside the old one.

Populating the allowlist
-------------------------
`_MF_SPKI_SHA256_PINS` below ships EMPTY. This package does not fabricate
cryptographic trust material — real fingerprints must be captured from an
operator-verified source before pinning can be enforced. To capture the current
pin for an environment:

    1. Fetch a known-good cert (out-of-band verified) via:
       GET https://api.ksef-test.mf.gov.pl/v2/security/public-key-certificates
       (or the production base URL), filtered to usage == "SymmetricKeyEncryption".
    2. Decode the Base64 DER certificate and compute its SPKI SHA-256 fingerprint:
       openssl x509 -inform DER -in cert.der -pubkey -noout \\
         | openssl pkey -pubin -outform DER \\
         | openssl dgst -sha256
    3. Add the resulting hex digest to `_MF_SPKI_SHA256_PINS[environment]`.

Until at least one pin is configured for the active environment, pinning is
inert: `verify_mf_spki_pin` is a no-op unless `enforce=True` is passed AND the
allowlist for that environment is non-empty. This is deliberate — enforcing
against an empty allowlist would lock out every submission, which is worse
than the residual risk being tracked.
"""

from __future__ import annotations

import hashlib

from cryptography import x509
from cryptography.hazmat.primitives import serialization

# [NEED: verify] — populate with operator-verified SPKI SHA-256 fingerprints
# per environment before enabling KSEF_VERIFY_MF_KEY_PINNING. See module
# docstring for the capture procedure. Intentionally empty at ship time.
_MF_SPKI_SHA256_PINS: dict[str, frozenset[str]] = {
    "test": frozenset(),
    "production": frozenset(),
}


class MFKeyPinningError(Exception):
    """Raised when the Ministry of Finance certificate fails SPKI pin verification."""


def compute_spki_sha256_hex(cert_der: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of a DER certificate's SubjectPublicKeyInfo."""
    cert = x509.load_der_x509_certificate(cert_der)
    spki_der = cert.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(spki_der).hexdigest()


def verify_mf_spki_pin(cert_der: bytes, environment: str, *, enforce: bool) -> None:
    """Verify *cert_der*'s SPKI fingerprint against the allowlist for *environment*.

    No-op when `enforce` is False, or when the allowlist for *environment* is
    empty (no pins have been configured yet — see module docstring).

    Raises:
        MFKeyPinningError: If enforcement is active, pins exist for the
            environment, and the certificate's fingerprint is not among them.
    """
    if not enforce:
        return
    pins = _MF_SPKI_SHA256_PINS.get(environment, frozenset())
    if not pins:
        return
    fingerprint = compute_spki_sha256_hex(cert_der)
    if fingerprint not in pins:
        raise MFKeyPinningError(
            f"KSeF Ministry of Finance certificate SPKI fingerprint {fingerprint!r} "
            f"is not in the pinned allowlist for environment {environment!r}. "
            "Refusing to encrypt against an unpinned key."
        )
