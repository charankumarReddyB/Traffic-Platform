"""Initial migration: complete schema for traffic platform.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-22 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=160), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='user'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('amb_code', sa.String(length=32), nullable=True, unique=True),
        sa.Column('requested_role', sa.String(length=32), nullable=True),
        sa.Column('request_status', sa.String(length=32), nullable=True),
        sa.Column('request_note', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. sessions (persistent auth sessions)
    op.create_table(
        'sessions',
        sa.Column('token', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('expires_at', sa.Float(), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=True),
    )
    op.create_index('ix_sessions_token', 'sessions', ['token'], unique=False)
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'], unique=False)

    # 3. road_nodes (real OSM junctions)
    op.create_table(
        'road_nodes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('label', sa.String(length=120), nullable=True),
    )

    # 4. road_edges (real OSM road links)
    op.create_table(
        'road_edges',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('node_a', sa.Integer(), nullable=False),
        sa.Column('node_b', sa.Integer(), nullable=False),
        sa.Column('distance_km', sa.Float(), nullable=False),
        sa.Column('max_speed_kmh', sa.Float(), nullable=False, server_default='40.0'),
        sa.Column('centrality', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('road_name', sa.String(length=160), nullable=True),
    )
    op.create_index('ix_road_edges_node_a', 'road_edges', ['node_a'], unique=False)
    op.create_index('ix_road_edges_node_b', 'road_edges', ['node_b'], unique=False)

    # 5. hospitals
    op.create_table(
        'hospitals',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
    )

    # 6. trips
    op.create_table(
        'trips',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('operator_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('hospital_id', sa.Integer(), nullable=False),
        sa.Column('src', sa.Integer(), nullable=False),
        sa.Column('dst', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='Ready'),
        sa.Column('severity', sa.String(length=32), server_default='routine'),
        sa.Column('est_minutes', sa.Float(), server_default='0.0'),
        sa.Column('km', sa.Float(), server_default='0.0'),
        sa.Column('started_at', sa.String(length=64), nullable=True),
        sa.Column('completed_at', sa.String(length=64), nullable=True),
    )
    op.create_index('ix_trips_operator_id', 'trips', ['operator_id'], unique=False)

    # 7. location_updates
    op.create_table(
        'location_updates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('trip_id', sa.Integer(), sa.ForeignKey('trips.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('speed', sa.Float(), nullable=True),
        sa.Column('heading', sa.Float(), nullable=True),
        sa.Column('recorded_at', sa.String(length=64), nullable=True),
    )
    op.create_index('ix_location_updates_trip_id', 'location_updates', ['trip_id'], unique=False)

    # 8. scenarios
    op.create_table(
        'scenarios',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('config', sa.Text(), nullable=False),
        sa.Column('result', sa.Text(), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=True),
    )

    # 9. traffic_observations
    op.create_table(
        'traffic_observations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('road_id', sa.Integer(), nullable=False),
        sa.Column('observed_at', sa.String(length=64), nullable=False),
        sa.Column('speed_kmh', sa.Float(), nullable=False),
        sa.Column('free_speed_kmh', sa.Float(), nullable=False),
        sa.Column('load', sa.Float(), nullable=False),
        sa.Column('congestion_level', sa.String(length=16), server_default='green'),
        sa.Column('data_source', sa.String(length=32), server_default='simulated'),
    )
    op.create_index('ix_traffic_observations_road_id', 'traffic_observations', ['road_id'], unique=False)
    op.create_index('ix_traffic_observations_observed_at', 'traffic_observations', ['observed_at'], unique=False)

    # 10. bus_routes
    op.create_table(
        'bus_routes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=120), nullable=False, unique=True),
        sa.Column('operator_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('nodes', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='active'),
        sa.Column('created_at', sa.String(length=64), nullable=True),
    )

    # 11. bus_stops
    op.create_table(
        'bus_stops',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('node', sa.Integer(), nullable=False),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lon', sa.Float(), nullable=True),
        sa.UniqueConstraint('name', 'node', name='uq_bus_stop_name_node'),
    )

    # 12. bus_route_stops
    op.create_table(
        'bus_route_stops',
        sa.Column('route_id', sa.Integer(), sa.ForeignKey('bus_routes.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('stop_id', sa.Integer(), sa.ForeignKey('bus_stops.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('seq', sa.Integer(), primary_key=True),
    )

    # 13. bus_schedules
    op.create_table(
        'bus_schedules',
        sa.Column('route_id', sa.Integer(), sa.ForeignKey('bus_routes.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('first', sa.String(length=16), nullable=False),
        sa.Column('last', sa.String(length=16), nullable=False),
        sa.Column('headway', sa.Float(), nullable=False),
        sa.Column('fleet', sa.Integer(), nullable=False),
    )

    # 14. proposals
    op.create_table(
        'proposals',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('route_id', sa.Integer(), sa.ForeignKey('bus_routes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('operator_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('kind', sa.String(length=32), server_default='route'),
        sa.Column('nodes', sa.Text(), nullable=True),
        sa.Column('schedule', sa.Text(), nullable=True),
        sa.Column('note', sa.String(length=300), server_default=''),
        sa.Column('preview', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='pending'),
        sa.Column('created_at', sa.String(length=64), nullable=True),
    )

    # 15. audit
    op.create_table(
        'audit',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=256), nullable=False),
        sa.Column('at', sa.String(length=64), nullable=True),
    )

    # 16. model_versions
    op.create_table(
        'model_versions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('version_tag', sa.String(length=64), nullable=False, unique=True),
        sa.Column('model_type', sa.String(length=64), nullable=False),
        sa.Column('trained_at', sa.String(length=64), nullable=True),
        sa.Column('n_train', sa.Integer(), nullable=False),
        sa.Column('n_test', sa.Integer(), nullable=False),
        sa.Column('metrics', sa.Text(), nullable=False),
        sa.Column('file_path', sa.String(length=256), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='0'),
    )

def downgrade() -> None:
    op.drop_table('model_versions')
    op.drop_table('audit')
    op.drop_table('proposals')
    op.drop_table('bus_schedules')
    op.drop_table('bus_route_stops')
    op.drop_table('bus_stops')
    op.drop_table('bus_routes')
    op.drop_table('traffic_observations')
    op.drop_table('scenarios')
    op.drop_table('location_updates')
    op.drop_table('trips')
    op.drop_table('hospitals')
    op.drop_table('road_edges')
    op.drop_table('road_nodes')
    op.drop_table('sessions')
    op.drop_table('users')
