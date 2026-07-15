"""Tests for the PL-3.6 SPKI SHA-256 pinning mechanism.

The shipped allowlist is intentionally empty (see security/mf_pinning.py
docstring — this package does not fabricate cryptographic trust material),
so these tests exercise the mechanism itself: no-op behaviour with an empty
allowlist, and enforcement once a pin is injected.
"""

import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from mcp_ksef_pl.security import mf_pinning
from mcp_ksef_pl.security.mf_pinning import (
    MFKeyPinningError,
    compute_spki_sha256_hex,
    verify_mf_spki_pin,
)


def _make_self_signed_cert_der() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "mf-pinning-test")]
    )
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.DER)


class TestVerifyMfSpkiPin:
    def test_no_op_when_enforce_false(self) -> None:
        cert_der = _make_self_signed_cert_der()
        # Should not raise even though no pins exist.
        verify_mf_spki_pin(cert_der, "test", enforce=False)

    def test_no_op_when_allowlist_empty(self) -> None:
        cert_der = _make_self_signed_cert_der()
        # enforce=True but the shipped allowlist is empty -> still a no-op.
        verify_mf_spki_pin(cert_der, "test", enforce=True)

    def test_raises_when_fingerprint_not_pinned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cert_der = _make_self_signed_cert_der()
        monkeypatch.setitem(
            mf_pinning._MF_SPKI_SHA256_PINS, "test", frozenset({"deadbeef"})
        )
        with pytest.raises(MFKeyPinningError, match="not in the pinned allowlist"):
            verify_mf_spki_pin(cert_der, "test", enforce=True)

    def test_passes_when_fingerprint_pinned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cert_der = _make_self_signed_cert_der()
        fingerprint = compute_spki_sha256_hex(cert_der)
        monkeypatch.setitem(
            mf_pinning._MF_SPKI_SHA256_PINS, "test", frozenset({fingerprint})
        )
        verify_mf_spki_pin(cert_der, "test", enforce=True)
