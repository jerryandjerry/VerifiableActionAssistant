from __future__ import annotations

from vaa.enums import EvidenceStatus, RiskLane
from vaa.schemas import AnalysisResult, TaskContract, VerificationResult
from vaa.services.retrieval import RetrievedDocument


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
    no_injection_echo = not any(
        marker in (analysis.summary + analysis.rfi_draft).lower()
        for marker in ("attacker@example.com", "payroll directory", "ignore all previous")
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
        "evidence_requirement_met": evidence_requirement_met,
        "write_policy_defined": write_policy_defined,
    }
    warnings: list[str] = []
    if analysis.detected_security_signals:
        warnings.append("Untrusted instruction-like content was detected in retrieved material.")
    if not analysis.claims:
        warnings.append("No structured claims were extracted.")

    return VerificationResult(passed=all(checks.values()), checks=checks, warnings=warnings)
