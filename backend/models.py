"""SQLAlchemy models for the Traffic, Public Transport & Emergency Platform.
Supports PostgreSQL and SQLite.
"""
import datetime as dt
from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean, ForeignKey, UniqueConstraint, Index, DateTime
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def utcnow_str():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    email = Column(String(160), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False, default="user") # user, bus_operator, ambulance, admin
    status = Column(String(32), nullable=False, default="active") # active, suspended
    amb_code = Column(String(32), unique=True, nullable=True)
    requested_role = Column(String(32), nullable=True)
    request_status = Column(String(32), nullable=True) # pending, approved, rejected
    request_note = Column(String(300), nullable=True)
    created_at = Column(String(64), default=utcnow_str)

    sessions = relationship("SessionToken", back_populates="user", cascade="all, delete-orphan")
    trips = relationship("Trip", back_populates="operator")
    routes = relationship("BusRoute", back_populates="operator")
    proposals = relationship("Proposal", back_populates="operator")

class SessionToken(Base):
    __tablename__ = "sessions"
    token = Column(String(64), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(Float, nullable=False)
    created_at = Column(String(64), default=utcnow_str)

    user = relationship("User", back_populates="sessions")

class RoadNode(Base):
    __tablename__ = "road_nodes"
    id = Column(Integer, primary_key=True) # junction node id
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    label = Column(String(120), nullable=True)

class RoadEdge(Base):
    __tablename__ = "road_edges"
    id = Column(Integer, primary_key=True) # edge id
    node_a = Column(Integer, nullable=False, index=True)
    node_b = Column(Integer, nullable=False, index=True)
    distance_km = Column(Float, nullable=False)
    max_speed_kmh = Column(Float, nullable=False, default=40.0)
    centrality = Column(Float, nullable=False, default=0.5)
    road_name = Column(String(160), nullable=True)

class Hospital(Base):
    __tablename__ = "hospitals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(160), nullable=False)
    node_id = Column(Integer, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True, autoincrement=True)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    hospital_id = Column(Integer, nullable=False)
    src = Column(Integer, nullable=False)
    dst = Column(Integer, nullable=False)
    status = Column(String(32), default="Ready") # Ready, Active, Completed, Cancelled
    severity = Column(String(32), default="routine") # critical, urgent, routine
    est_minutes = Column(Float, default=0.0)
    km = Column(Float, default=0.0)
    started_at = Column(String(64), nullable=True)
    completed_at = Column(String(64), nullable=True)

    operator = relationship("User", back_populates="trips")
    locations = relationship("LocationUpdate", back_populates="trip", cascade="all, delete-orphan")

class LocationUpdate(Base):
    __tablename__ = "location_updates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    speed = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    recorded_at = Column(String(64), default=utcnow_str)

    trip = relationship("Trip", back_populates="locations")

class Scenario(Base):
    __tablename__ = "scenarios"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(120), nullable=False)
    config = Column(Text, nullable=False) # JSON
    result = Column(Text, nullable=False) # JSON
    created_at = Column(String(64), default=utcnow_str)

class TrafficObservation(Base):
    __tablename__ = "traffic_observations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    road_id = Column(Integer, nullable=False, index=True)
    observed_at = Column(String(64), nullable=False, index=True)
    speed_kmh = Column(Float, nullable=False)
    free_speed_kmh = Column(Float, nullable=False)
    load = Column(Float, nullable=False)
    congestion_level = Column(String(16), default="green") # green, yellow, red
    data_source = Column(String(32), default="simulated") # tomtom_live, simulated, historical

class BusRoute(Base):
    __tablename__ = "bus_routes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), unique=True, nullable=False)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    nodes = Column(Text, nullable=False) # JSON list of junction ids
    status = Column(String(32), default="active")
    created_at = Column(String(64), default=utcnow_str)

    operator = relationship("User", back_populates="routes")
    schedule = relationship("BusSchedule", back_populates="route", uselist=False, cascade="all, delete-orphan")
    stops = relationship("BusRouteStop", back_populates="route", cascade="all, delete-orphan")

class BusStop(Base):
    __tablename__ = "bus_stops"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    node = Column(Integer, nullable=False)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    __table_args__ = (UniqueConstraint("name", "node", name="uq_bus_stop_name_node"),)

class BusRouteStop(Base):
    __tablename__ = "bus_route_stops"
    route_id = Column(Integer, ForeignKey("bus_routes.id", ondelete="CASCADE"), primary_key=True)
    stop_id = Column(Integer, ForeignKey("bus_stops.id", ondelete="CASCADE"), primary_key=True)
    seq = Column(Integer, primary_key=True)

    route = relationship("BusRoute", back_populates="stops")
    stop = relationship("BusStop")

class BusSchedule(Base):
    __tablename__ = "bus_schedules"
    route_id = Column(Integer, ForeignKey("bus_routes.id", ondelete="CASCADE"), primary_key=True)
    first = Column(String(16), nullable=False) # HH:MM
    last = Column(String(16), nullable=False) # HH:MM
    headway = Column(Float, nullable=False) # headway_min
    fleet = Column(Integer, nullable=False)

    route = relationship("BusRoute", back_populates="schedule")

class Proposal(Base):
    __tablename__ = "proposals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("bus_routes.id", ondelete="CASCADE"), nullable=False)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String(32), default="route") # route, schedule
    nodes = Column(Text, nullable=True) # JSON
    schedule = Column(Text, nullable=True) # JSON
    note = Column(String(300), default="")
    preview = Column(Text, nullable=True) # JSON
    status = Column(String(32), default="pending") # pending, approved, rejected
    created_at = Column(String(64), default=utcnow_str)

    operator = relationship("User", back_populates="proposals")

class AuditLog(Base):
    __tablename__ = "audit"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String(256), nullable=False)
    at = Column(String(64), default=utcnow_str)

class ModelVersion(Base):
    __tablename__ = "model_versions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    version_tag = Column(String(64), unique=True, nullable=False)
    model_type = Column(String(64), nullable=False) # RandomForestRegressor, GradientBoostingRegressor
    trained_at = Column(String(64), default=utcnow_str)
    n_train = Column(Integer, nullable=False)
    n_test = Column(Integer, nullable=False)
    metrics = Column(Text, nullable=False) # JSON: MAE, RMSE, CIs, baselines
    file_path = Column(String(256), nullable=True)
    is_active = Column(Boolean, default=False)
