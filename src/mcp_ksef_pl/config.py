from enum import StrEnum

from pydantic_settings import BaseSettings, SettingsConfigDict


class KSeFEnvironment(StrEnum):
    PRODUCTION = "production"
    TEST = "test"


# KSeF API v2 base URLs (api.ksef.mf.gov.pl/v2).
# The v1 domain (ksef.mf.gov.pl/api) and the demo environment are not part of v2.
_BASE_URLS: dict[KSeFEnvironment, str] = {
    KSeFEnvironment.PRODUCTION: "https://api.ksef.mf.gov.pl/v2",
    KSeFEnvironment.TEST: "https://api.ksef-test.mf.gov.pl/v2",
}


class KSeFSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KSEF_", env_file=".env", extra="ignore")

    environment: KSeFEnvironment = KSeFEnvironment.TEST

    # KSeF v2 AccessToken supplied by the caller.
    # Obtain it via the challenge → authenticate → redeem flow documented at
    # https://github.com/CIRFMF/ksef-docs/blob/main/uwierzytelnianie.md
    # Pass as KSEF_SESSION_TOKEN env var or via the session_token tool parameter.
    session_token: str = ""

    # NIP of the entity on whose behalf requests are sent (required by KSeF API).
    nip: str = ""

    timeout: int = 30

    # PL-3.6: enforce SPKI SHA-256 pinning on the MF SymmetricKeyEncryption
    # certificate (see security/mf_pinning.py). No-op until pins are populated
    # for the active environment, even when this is set to True.
    verify_mf_key_pinning: bool = False

    @property
    def base_url(self) -> str:
        return _BASE_URLS[self.environment]
