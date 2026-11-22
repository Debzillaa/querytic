from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

readonly_engine = create_engine(
    settings.readonly_database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ReadOnlySessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=readonly_engine,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """Read-write DB session for uploads and metadata operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_readonly_db() -> Generator[Session, None, None]:
    """Least-privilege read-only DB session for LLM-generated analytical queries."""
    db = ReadOnlySessionLocal()
    try:
        yield db
    finally:
        db.close()