import os
from sshtunnel import SSHTunnelForwarder
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from dotenv import load_dotenv

load_dotenv()

SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT", "22"))
SSH_USER = os.getenv("SSH_USER")
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH")
SSH_LOCAL_PORT = int(os.getenv("SSH_LOCAL_PORT", "3307"))

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

Base = declarative_base()

_tunnel: SSHTunnelForwarder | None = None
engine = None
SessionLocal = None


def start_tunnel_and_engine():
    global _tunnel, engine, SessionLocal

    if _tunnel is not None and _tunnel.is_active:
        return

    _tunnel = SSHTunnelForwarder(
        (SSH_HOST, SSH_PORT),
        ssh_username=SSH_USER,
        ssh_pkey=SSH_KEY_PATH,
        remote_bind_address=(DB_HOST, DB_PORT),
        local_bind_address=("127.0.0.1", SSH_LOCAL_PORT),
        set_keepalive=30.0,
    )
    _tunnel.start()

    db_url = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}"
        f"@127.0.0.1:{_tunnel.local_bind_port}/{DB_NAME}"
        "?charset=utf8mb4"
    )
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=2,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def stop_tunnel():
    global _tunnel
    if _tunnel is not None:
        _tunnel.stop()
        _tunnel = None


def get_db():
    if SessionLocal is None:
        start_tunnel_and_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
