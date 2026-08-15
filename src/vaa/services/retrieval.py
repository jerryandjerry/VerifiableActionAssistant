from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from vaa.models import Document
from vaa.services.security import scan_untrusted_content


@dataclass(frozen=True, slots=True)
class RetrievedDocument:
    id: str
    tenant_id: str
    project_id: str
    doc_type: str
    title: str
    version: int
    status: str
    trust_level: str
    approved_at: datetime | None
    content: str
    security_signals: list[str]
    score: float


_TOKEN_RE = re.compile(r"[a-zA-Z0-9.]+")
_STOPWORDS = {
    "the", "and", "for", "this", "that", "with", "from", "into", "latest",
    "project", "documents", "document", "identify", "draft", "rfi", "review",
    "compare", "requirement", "requirements", "every", "including",
}


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(text)
        if len(token) > 2 and token.lower() not in _STOPWORDS
    }


def _latest_approved_documents(session: Session, tenant_id: str, project_id: str) -> list[Document]:
    rows = session.scalars(
        select(Document).where(
            Document.tenant_id == tenant_id,
            Document.project_id == project_id,
            Document.status == "approved",
        )
    ).all()
    latest: dict[str, Document] = {}
    for document in rows:
        current = latest.get(document.doc_type)
        if current is None or document.version > current.version:
            latest[document.doc_type] = document
    return list(latest.values())


def retrieve_documents(
    session: Session,
    *,
    tenant_id: str,
    project_id: str,
    query: str,
    max_documents: int = 8,
) -> list[RetrievedDocument]:
    query_tokens = _tokens(query)
    candidates = _latest_approved_documents(session, tenant_id, project_id)
    scored: list[RetrievedDocument] = []

    for document in candidates:
        scan = scan_untrusted_content(document.content)
        searchable = f"{document.title} {document.doc_type} {scan.sanitized_content}"
        doc_tokens = _tokens(searchable)
        overlap = len(query_tokens & doc_tokens)
        title_overlap = len(query_tokens & _tokens(document.title))
        score = overlap + (title_overlap * 2.0)
        scored.append(
            RetrievedDocument(
                id=document.id,
                tenant_id=document.tenant_id,
                project_id=document.project_id,
                doc_type=document.doc_type,
                title=document.title,
                version=document.version,
                status=document.status,
                trust_level=document.trust_level,
                approved_at=document.approved_at,
                content=scan.sanitized_content,
                security_signals=scan.signals,
                score=score,
            )
        )

    scored.sort(key=lambda item: (item.score, item.version), reverse=True)
    matched = [item for item in scored if item.score > 0]
    if matched:
        return matched[:max_documents]
    return scored[: min(3, max_documents)]
