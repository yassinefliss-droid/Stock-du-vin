from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.assistant import agent
from app.database import get_db
from app.deps import get_current_user
from app.schemas import Question, ReponseAssistant

router = APIRouter(
    prefix="/api/assistant", tags=["assistant"], dependencies=[Depends(get_current_user)]
)


@router.post("/ask", response_model=ReponseAssistant)
def poser_question(q: Question, db: Session = Depends(get_db)):
    """Question en français sur le stock. Le modèle choisit un outil en lecture seule."""
    r = agent.repondre(db, q.question)
    return ReponseAssistant(reponse=r.texte, mode=r.mode, outils=r.outils)
