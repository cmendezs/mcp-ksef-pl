from enum import Enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class KSeFEnvironment(str, Enum):
    PRODUCTION = "production"
    TEST = "test"
    DEMO = "demo"


_BASE_URLS: dict[KSeFEnvironment, str] = {
    KSeFEnvironment.PRODUCTION: "https://ksef.mf.gov.pl/api",
    KSeFEnvironment.TEST: "https://ksef-test.mf.gov.pl/api",
    KSeFEnvironment.DEMO: "https://ksef-demo.mf.gov.pl/api",
}


class KSeFSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KSEF_", env_file=".env", extra="ignore")

    environment: KSeFEnvironment = KSeFEnvironment.TEST

    # Session token supplied by the caller (obtained via KSeF auth challenge flow).
    # For automated flows the caller must perform the challenge-response sign step
    # separately (qualified e-signature or token from the MF portal) and pass the
    # resulting sessionToken here.
    session_token: str = ""

    # NIP of the entity on whose behalf requests are sent (required by KSeF API).
    nip: str = ""

    timeout: int = 30

    @property
    def base_url(self) -> str:
        return _BASE_URLS[self.environment]
