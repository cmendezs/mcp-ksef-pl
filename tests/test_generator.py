"""Tests for the FA(2) and FA(3) XML generators."""

from decimal import Decimal

import pytest
from mcp_einvoicing_core import DocumentGenerationError
from mcp_einvoicing_core.en16931 import EN16931Tax

from mcp_ksef_pl.generator import FA2Generator, FA3Generator
from mcp_ksef_pl.models import KSeFInvoice

_NS = "http://crd.gov.pl/wzor/2023/06/29/12648/"
_NS3 = "http://crd.gov.pl/wzor/2025/06/25/13775/"


class TestFA2Generator:
    @pytest.fixture
    def generator(self) -> FA2Generator:
        return FA2Generator()

    def test_format_metadata(self, generator: FA2Generator) -> None:
        assert generator.get_format_name() == "FA(2)"
        assert generator.get_country_code() == "PL"
        assert generator.get_namespace() == _NS

    @pytest.mark.asyncio
    async def test_generate_contains_namespace(
        self, generator: FA2Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert _NS in xml

    @pytest.mark.asyncio
    async def test_generate_header_fields(
        self, generator: FA2Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<KodFormularza" in xml
        assert "FA (2)" in xml
        assert "<WariantFormularza>2</WariantFormularza>" in xml
        assert "<DataWytworzeniaFa>" in xml

    @pytest.mark.asyncio
    async def test_generate_seller_nip(
        self, generator: FA2Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<Podmiot1>" in xml
        assert "<NIP>5261040828</NIP>" in xml

    @pytest.mark.asyncio
    async def test_generate_buyer(
        self, generator: FA2Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<Podmiot2>" in xml

    @pytest.mark.asyncio
    async def test_generate_invoice_fields(
        self, generator: FA2Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<P_1>2024-03-15</P_1>" in xml
        assert "<P_2>FV/2024/001</P_2>" in xml
        assert "<KodWaluty>PLN</KodWaluty>" in xml

    @pytest.mark.asyncio
    async def test_generate_vat_fields(
        self, generator: FA2Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        # 23% VAT → P_13_1, P_14_1
        assert "<P_13_1>2000.00</P_13_1>" in xml
        assert "<P_14_1>460.00</P_14_1>" in xml
        assert "<P_15>2460.00</P_15>" in xml

    @pytest.mark.asyncio
    async def test_generate_invoice_lines(
        self, generator: FA2Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        # FA(2) has no <FaWiersze> wrapper either — verified against
        # schemat_FA(2)_v1-0E.xsd; <FaWiersz> is a direct child of <Fa>.
        assert "FaWiersze" not in xml
        assert "<FaWiersz>" in xml
        assert "<P_7>Usługi konsultingowe</P_7>" in xml

    @pytest.mark.asyncio
    async def test_generate_adnotacje_and_rodzaj_faktury(
        self, generator: FA2Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<Zwolnienie>" in xml
        assert "<P_19N>1</P_19N>" in xml
        assert "<RodzajFaktury>VAT</RodzajFaktury>" in xml

    @pytest.mark.asyncio
    async def test_generate_note(
        self, generator: FA2Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<StopkaFaktury>" in xml
        assert "Termin płatności" in xml

    @pytest.mark.asyncio
    async def test_unknown_vat_rate_raises(
        self, generator: FA2Generator, sample_invoice: KSeFInvoice
    ) -> None:
        for bad_rate in (Decimal("7"), Decimal("22")):
            invoice = sample_invoice.model_copy(
                update={
                    "tax_lines": [
                        EN16931Tax(
                            category="S",
                            rate=bad_rate,
                            taxable_amount=Decimal("2000.00"),
                            tax_amount=Decimal("140.00"),
                        )
                    ]
                }
            )
            with pytest.raises(DocumentGenerationError, match="Unknown standard-category"):
                await generator.generate(invoice)

    @pytest.mark.asyncio
    async def test_payment_block_nests_inside_platnosc(
        self, generator: FA2Generator, sample_invoice: KSeFInvoice
    ) -> None:
        """PL-PAY-1: due_date/IBAN must nest inside <Platnosc>, not a raw <P_6>."""
        from datetime import date

        from mcp_einvoicing_core.en16931 import EN16931PaymentMeans

        invoice = sample_invoice.model_copy(
            update={
                "due_date": date(2024, 4, 15),
                "payment_means": EN16931PaymentMeans(
                    type_code="58", iban="PL61109010140000071219812874"
                ),
            }
        )
        xml = await generator.generate(invoice)

        assert "<P_6>" not in xml
        assert "<Platnosc>" in xml
        platnosc_start = xml.index("<Platnosc>")
        platnosc_end = xml.index("</Platnosc>")
        platnosc_block = xml[platnosc_start:platnosc_end]

        assert "<TerminPlatnosci>" in platnosc_block
        assert "<Termin>2024-04-15</Termin>" in platnosc_block
        assert "<RachunekBankowy>" in platnosc_block
        assert "<NrRB>PL61109010140000071219812874</NrRB>" in platnosc_block

        # FormaPlatnosci must NOT be nested inside TerminPlatnosci (mirrors PL-2.7 for FA3).
        termin_start = xml.index("<TerminPlatnosci>")
        termin_end = xml.index("</TerminPlatnosci>")
        assert "FormaPlatnosci" not in xml[termin_start:termin_end]
        assert "<FormaPlatnosci>6</FormaPlatnosci>" in xml
        assert termin_end < xml.index("<FormaPlatnosci>")

        # <Platnosc> is a sibling of <FaWiersz>, positioned after the invoice lines.
        assert xml.index("<FaWiersz>") < platnosc_start

    @pytest.mark.asyncio
    async def test_no_payment_data_omits_platnosc(
        self, generator: FA2Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<Platnosc>" not in xml


class TestFA3Generator:
    @pytest.fixture
    def generator(self) -> FA3Generator:
        return FA3Generator()

    def test_format_metadata(self, generator: FA3Generator) -> None:
        assert generator.get_format_name() == "FA(3)"
        assert generator.get_country_code() == "PL"
        assert generator.get_namespace() == _NS3

    @pytest.mark.asyncio
    async def test_namespace(self, generator: FA3Generator, sample_invoice: KSeFInvoice) -> None:
        xml = await generator.generate(sample_invoice)
        assert _NS3 in xml
        # FA(2) namespace must NOT appear
        assert _NS not in xml

    @pytest.mark.asyncio
    async def test_header_fields(
        self, generator: FA3Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert 'kodSystemowy="FA (3)"' in xml
        assert "<WariantFormularza>3</WariantFormularza>" in xml
        # Correct field name (not the FA(2) typo DataWytworzenieFa)
        assert "<DataWytworzeniaFa>" in xml
        assert "DataWytworzenieFa" not in xml

    @pytest.mark.asyncio
    async def test_seller_nip(self, generator: FA3Generator, sample_invoice: KSeFInvoice) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<Podmiot1>" in xml
        assert "<NIP>5261040828</NIP>" in xml

    @pytest.mark.asyncio
    async def test_buyer_has_jst_and_gv_flags(
        self, generator: FA3Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<Podmiot2>" in xml
        # Both mandatory FA(3) flags must be present with value 2 (not applicable)
        assert "<JST>2</JST>" in xml
        assert "<GV>2</GV>" in xml

    @pytest.mark.asyncio
    async def test_address_uses_adresl1(
        self, generator: FA3Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        # TAdres in FA(3) uses AdresL1 (composed) — no KodPocztowy or Miejscowosc
        assert "<AdresL1>" in xml
        assert "KodPocztowy" not in xml
        assert "Miejscowosc" not in xml

    @pytest.mark.asyncio
    async def test_invoice_fields(
        self, generator: FA3Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<P_1>2024-03-15</P_1>" in xml
        assert "<P_2>FV/2024/001</P_2>" in xml
        assert "<KodWaluty>PLN</KodWaluty>" in xml

    @pytest.mark.asyncio
    async def test_vat_fields(self, generator: FA3Generator, sample_invoice: KSeFInvoice) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<P_13_1>2000.00</P_13_1>" in xml
        assert "<P_14_1>460.00</P_14_1>" in xml
        assert "<P_15>2460.00</P_15>" in xml

    @pytest.mark.asyncio
    async def test_adnotacje_structure(
        self, generator: FA3Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<Adnotacje>" in xml
        # Mandatory sub-elements absent from FA(2) generator
        assert "<Zwolnienie>" in xml
        assert "<P_19N>1</P_19N>" in xml
        assert "<NoweSrodkiTransportu>" in xml
        assert "<P_22N>1</P_22N>" in xml
        assert "<PMarzy>" in xml
        assert "<P_PMarzyN>1</P_PMarzyN>" in xml

    @pytest.mark.asyncio
    async def test_rodzaj_faktury_present(
        self, generator: FA3Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<RodzajFaktury>VAT</RodzajFaktury>" in xml

    @pytest.mark.asyncio
    async def test_no_fawiersze_wrapper(
        self, generator: FA3Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        # FA(3) has no <FaWiersze> wrapper — lines are direct <FaWiersz> children of <Fa>
        assert "FaWiersze" not in xml
        assert "<FaWiersz>" in xml
        assert "<P_7>Usługi konsultingowe</P_7>" in xml

    @pytest.mark.asyncio
    async def test_note_in_stopka(
        self, generator: FA3Generator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        # Note must be in <Stopka><Informacje>, not inside <Fa>
        assert "<Stopka>" in xml
        assert "<Informacje>" in xml
        assert "<StopkaFaktury>" in xml
        assert "Termin płatności" in xml
        # Verify ordering: </Fa> comes before <Stopka>
        assert xml.index("</Fa>") < xml.index("<Stopka>")

    @pytest.mark.asyncio
    async def test_no_note_omits_stopka(
        self,
        generator: FA3Generator,
        sample_invoice: KSeFInvoice,
    ) -> None:
        invoice_no_note = sample_invoice.model_copy(update={"note": None})
        xml = await generator.generate(invoice_no_note)
        assert "<Stopka>" not in xml

    @pytest.mark.asyncio
    async def test_unknown_vat_rate_raises(
        self, generator: FA3Generator, sample_invoice: KSeFInvoice
    ) -> None:
        for bad_rate in (Decimal("7"), Decimal("22")):
            invoice = sample_invoice.model_copy(
                update={
                    "tax_lines": [
                        EN16931Tax(
                            category="S",
                            rate=bad_rate,
                            taxable_amount=Decimal("2000.00"),
                            tax_amount=Decimal("140.00"),
                        )
                    ]
                }
            )
            with pytest.raises(DocumentGenerationError, match="Unknown standard-category"):
                await generator.generate(invoice)

    @pytest.mark.asyncio
    async def test_payment_block_forma_platnosci_is_sibling_of_termin_platnosci(
        self, generator: FA3Generator, sample_invoice: KSeFInvoice
    ) -> None:
        from datetime import date

        from mcp_einvoicing_core.en16931 import EN16931PaymentMeans

        invoice = sample_invoice.model_copy(
            update={
                "due_date": date(2024, 4, 15),
                "payment_means": EN16931PaymentMeans(
                    type_code="58", iban="PL61109010140000071219812874"
                ),
            }
        )
        xml = await generator.generate(invoice)
        # FormaPlatnosci must NOT be nested inside TerminPlatnosci (PL-2.7).
        termin_start = xml.index("<TerminPlatnosci>")
        termin_end = xml.index("</TerminPlatnosci>")
        assert "FormaPlatnosci" not in xml[termin_start:termin_end]
        assert "<FormaPlatnosci>6</FormaPlatnosci>" in xml
        assert termin_end < xml.index("<FormaPlatnosci>")

    @pytest.mark.asyncio
    async def test_link_do_platnosci_before_ipksef(
        self, generator: FA3Generator, sample_invoice: KSeFInvoice
    ) -> None:
        from mcp_ksef_pl.models import KSeFFA3Options

        options = KSeFFA3Options(
            ipksef="001AB12345678",
            link_do_platnosci="https://platnosc.ksef.mf.gov.pl/pay?IPKSeF=001AB12345678",
        )
        xml = await generator.generate(sample_invoice, options=options)
        assert xml.index("<LinkDoPlatnosci>") < xml.index("<IPKSeF>")


class TestDiscouragedCharacterSanitization:
    """PL-DISC-1: KSeF API v2.4.0+ rejects W3C-discouraged code points that
    xml_escape() alone lets through (mcp-einvoicing-core v1.27.0, sanitize_xml_text)."""

    @pytest.mark.asyncio
    async def test_fa2_note_with_discouraged_char_raises(self, sample_invoice: KSeFInvoice) -> None:
        invoice = sample_invoice.model_copy(update={"note": "note with \x85 char"})
        with pytest.raises(DocumentGenerationError):
            await FA2Generator().generate(invoice)

    @pytest.mark.asyncio
    async def test_fa3_note_with_discouraged_char_raises(self, sample_invoice: KSeFInvoice) -> None:
        invoice = sample_invoice.model_copy(update={"note": "note with \x85 char"})
        with pytest.raises(DocumentGenerationError):
            await FA3Generator().generate(invoice)

    @pytest.mark.asyncio
    async def test_seller_name_with_discouraged_char_raises(
        self, sample_invoice: KSeFInvoice
    ) -> None:
        seller = sample_invoice.seller.model_copy(update={"name": "ACME\x7fSp. z o.o."})
        invoice = sample_invoice.model_copy(update={"seller": seller})
        with pytest.raises(DocumentGenerationError):
            await FA2Generator().generate(invoice)

    @pytest.mark.asyncio
    async def test_clean_invoice_is_unaffected(self, sample_invoice: KSeFInvoice) -> None:
        xml = await FA2Generator().generate(sample_invoice)
        assert "<Podmiot1>" in xml
