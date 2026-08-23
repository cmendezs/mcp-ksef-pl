"""Tests for KSeF-specific Pydantic model validators (PL-4.2, PL-2.6, PL-3.5)."""

from datetime import date

import pytest
from pydantic import ValidationError

from mcp_ksef_pl.models import KSeFAttachment, KSeFCorrectionRef, SubjectType


class TestKSeFCorrectionRef:
    def test_ksef_branch_valid(self) -> None:
        ref = KSeFCorrectionRef(
            data_wyst=date(2024, 1, 10),
            nr_fa_korygowanej="FV/2024/000",
            numer_ksef=True,
            nr_ksef_fa_korygowanej="5261040828-20240110-ABCDEF012345-CD",
        )
        assert ref.numer_ksef is True

    def test_ksefn_branch_valid(self) -> None:
        ref = KSeFCorrectionRef(
            data_wyst=date(2024, 1, 10),
            nr_fa_korygowanej="FV/2024/000",
            numer_ksefn=True,
        )
        assert ref.numer_ksefn is True

    def test_neither_branch_raises(self) -> None:
        with pytest.raises(ValidationError, match="requires either"):
            KSeFCorrectionRef(data_wyst=date(2024, 1, 10), nr_fa_korygowanej="FV/2024/000")

    def test_both_branches_raises(self) -> None:
        with pytest.raises(ValidationError, match="not both"):
            KSeFCorrectionRef(
                data_wyst=date(2024, 1, 10),
                nr_fa_korygowanej="FV/2024/000",
                numer_ksef=True,
                nr_ksef_fa_korygowanej="5261040828-20240110-ABCDEF012345-CD",
                numer_ksefn=True,
            )

    def test_numer_ksef_without_value_raises(self) -> None:
        with pytest.raises(ValidationError, match="requires nr_ksef_fa_korygowanej"):
            KSeFCorrectionRef(
                data_wyst=date(2024, 1, 10),
                nr_fa_korygowanej="FV/2024/000",
                numer_ksef=True,
            )


class TestKSeFAttachment:
    def test_requires_at_least_one_metadata_entry(self) -> None:
        with pytest.raises(ValidationError):
            KSeFAttachment(metadata=[])

    def test_valid_with_metadata_only(self) -> None:
        att = KSeFAttachment(metadata=[("okres", "2024-03")])
        assert att.metadata == [("okres", "2024-03")]


class TestSubjectType:
    def test_members(self) -> None:
        assert {m.value for m in SubjectType} == {
            "Subject1",
            "Subject2",
            "Subject3",
            "SubjectAuthorized",
        }
