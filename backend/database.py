"""Database configuration and session management.
Supports both PostgreSQL (via DATABASE_URL) and SQLite (via TRAFFIC_DB or sqlite:///traffic.db).
"""
import os, hashlib, secrets, datetime as dt
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base, User, SessionToken, RoadNode, RoadEdge, Hospital

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    db_file = os.environ.get("TRAFFIC_DB", "traffic.db")
    DATABASE_URL = f"sqlite:///{db_file}"

# Handle Postgres postgres:// URI schema from older tools
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

is_sqlite = DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if is_sqlite else {}
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False
)

# Enable foreign keys for SQLite
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
ScopedSession = scoped_session(SessionFactory)

@contextmanager
def get_db():
    """Provide a transactional scope around a series of operations."""
    session = ScopedSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def hash_pw(p: str, salt: bytes = None) -> str:
    salt = salt or os.urandom(16)
    return salt.hex() + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), salt, 200_000).hex()

def check_pw(p: str, h: str) -> bool:
    try:
        s = h.split("$")[0]
        return secrets.compare_digest(hash_pw(p, bytes.fromhex(s)), h)
    except Exception:
        return False

def init_db():
    """Create all tables and guarantee an admin account exists."""
    Base.metadata.create_all(bind=engine)
    with get_db() as session:
        admin_exists = session.query(User).filter(User.role == "admin").first()
        if not admin_exists:
            em = os.environ.get("ADMIN_EMAIL", "admin@example.com")
            pw = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(9)
            admin = User(
                name="Admin",
                email=em.lower(),
                password_hash=hash_pw(pw),
                role="admin",
                status="active",
                created_at=now()
            )
            session.add(admin)
            session.flush()
            print(f"[setup] admin created: {em} / {pw}")

def seed_network_into_db(nodes_dict, edges_dict, hospitals_dict):
    """Seed real OpenStreetMap road network and hospitals into the database."""
    with get_db() as session:
        # Check if already seeded
        if session.query(RoadNode).first() is None:
            node_objs = [
                RoadNode(id=n_id, lat=coords[0], lon=coords[1], label=f"Junction {n_id}")
                for n_id, coords in nodes_dict.items()
            ]
            session.bulk_save_objects(node_objs)
            
            edge_objs = [
                RoadEdge(
                    id=e["id"],
                    node_a=e["a"],
                    node_b=e["b"],
                    distance_km=e["km"],
                    max_speed_kmh=e["speed"],
                    centrality=e["centrality"],
                    road_name=f"Road {e['id']} ({e['a']} <-> {e['b']})"
                )
                for e in edges_dict.values()
            ]
            session.bulk_save_objects(edge_objs)
            
            hosp_objs = [
                Hospital(id=h_id, name=h_info[0], node_id=h_info[1],
                         lat=nodes_dict[h_info[1]][0], lon=nodes_dict[h_info[1]][1])
                for h_id, h_info in hospitals_dict.items()
            ]
            session.bulk_save_objects(hosp_objs)
            session.commit()
