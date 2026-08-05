"""
Gestion de la connexion et des sessions SQLAlchemy vers PostGIS.

Fournit un moteur unique, une fabrique de sessions et un utilitaire
`init_db()` qui active l'extension PostGIS et crée toutes les tables.
"""
from __future__ import annotations

from contextlib import contextmanager

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from src.db.models import Base

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Active PostGIS et crée les tables si elles n'existent pas."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
    Base.metadata.create_all(engine)
    logger.info("Base PostGIS initialisée (extension + tables).")


@contextmanager
def get_session():
    """Contexte de session transactionnelle (commit/rollback automatiques)."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
