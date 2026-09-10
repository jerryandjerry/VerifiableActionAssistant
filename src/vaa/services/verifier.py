from __future__ import annotations

from vaa.enums import EvidenceStatus, RiskLane
from vaa.schemas import AnalysisResult, TaskContract, VerificationResult
from vaa.services.retrieval import RetrievedDocument
from vaa.services.security import scan_untrusted_content


def _generated_text(analysis: AnalysisResult) -> str:
    values = [
        analysis.summary,
        *analysis.key_findings,
        analysis.rfi_subject,
        analysis.rfi_draft,
    ]
    for claim in analysis.claims:
        values.extend(
            [
                claim.claim_key,
                claim.claim_text,
                *(str(value) for value in claim.observed_values),
                *(str(conflict) for conflict in claim.conflicts),
            ]
        )
        for source in claim.sources:
            values.extend([source.title, source.section, source.excerpt])
    return "\n".join(values)


def verify_analysis(
    *,
    contract: TaskContract,
    analysis: AnalysisResult,
    documents: list[RetrievedDocument],
) -> VerificationResult:
    allowed_document_ids = {document.id for document in documents}
    source_ids = {source.document_id for claim in analysis.claims for source in claim.sources}
    all_sources_authorized = source_ids <= allowed_document_ids
    claims_have_sources = all(bool(claim.sources) for claim in analysis.claims)
    conflict_labels_match_values = all(
        (
            claim.status == EvidenceStatus.CONFLICTING
            if len({str(value) for value in claim.observed_values}) > 1
            else claim.status != EvidenceStatus.CONFLICTING
        )
        for claim in analysis.claims
    )
    no_injection_echo = not scan_untrusted_content(_generated_text(analysis)).signals
    expected_security_signals = sorted(
        {signal for document in documents for signal in document.security_signals}
    )
    security_signals_match_sources = (
        sorted(set(analysis.detected_security_signals)) == expected_security_signals
    )
    evidence_requirement_met = bool(analysis.claims) if contract.required_evidence else True
    write_policy_defined = (
        contract.approval_policy == "before_any_write"
        if contract.lane == RiskLane.ACTION_CONTROLLED
        else "jira.create_ticket" not in contract.allowed_tools
    )

    checks = {
        "all_sources_authorized": all_sources_authorized,
        "claims_have_sources": claims_have_sources,
        "conflict_labels_match_values": conflict_labels_match_values,
        "no_prompt_injection_echo": no_injection_echo,
        "security_signals_match_sources": security_signals_match_sources,
        "evidence_requirement_met": evidence_requirement_met,
        "write_policy_defined": write_policy_defined,
    }
    warnings: list[str] = []
    if expected_security_signals:
        warnings.append("Untrusted instruction-like content was detected in retrieved material.")
    if not analysis.claims:
        warnings.append("No structured claims were extracted.")

    return VerificationResult(passed=all(checks.values()), checks=checks, warnings=warnings)
