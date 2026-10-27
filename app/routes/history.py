from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DebugSession
from app.schemas import HistoryItem

router = APIRouter(prefix="/api/debug/history", tags=["History"])


@router.get("", response_model=List[HistoryItem], status_code=status.HTTP_200_OK)
def get_debugging_history(
    mode: Optional[str] = Query(None, description="Filter by mode: 'diagnosis' or 'smart_fallback'"),
    search: Optional[str] = Query(None, description="Search term matching endpoint or error summary"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieves paginated history of past debugging sessions."""
    query = db.query(DebugSession)

    if mode:
        query = query.filter(DebugSession.mode == mode)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (DebugSession.endpoint.ilike(search_pattern))
            | (DebugSession.error_summary.ilike(search_pattern))
            | (DebugSession.error_message.ilike(search_pattern))
        )

    records = query.order_by(DebugSession.id.asc()).offset(offset).limit(limit).all()

    return [
        HistoryItem(
            id=r.id,
            endpoint=r.endpoint,
            method=r.method,
            status_code=r.status_code,
            error_message=r.error_message,
            mode=r.mode,
            status=r.status,
            confidence=r.confidence,
            error_summary=r.error_summary,
            root_cause=r.root_cause,
            is_resolved=r.is_resolved,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in records
    ]


@router.get("/{session_id}", status_code=status.HTTP_200_OK)
def get_session_details(session_id: int, db: Session = Depends(get_db)):
    """Retrieves complete details for a specific debugging session by ID."""
    session_record = db.query(DebugSession).filter(DebugSession.id == session_id).first()
    if not session_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debugging session #{session_id} not found.",
        )
    return session_record.to_dict()


@router.delete("/{session_id}", status_code=status.HTTP_200_OK)
def delete_debugging_session(session_id: int, db: Session = Depends(get_db)):
    """Deletes a debugging session by ID."""
    session_record = db.query(DebugSession).filter(DebugSession.id == session_id).first()
    if not session_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debugging session #{session_id} not found.",
        )
    db.delete(session_record)
    db.commit()
    return {"message": f"Session #{session_id} successfully deleted.", "deleted_id": session_id}
