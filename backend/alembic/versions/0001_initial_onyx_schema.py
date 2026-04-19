"""Initial ONYX schema creation.

Revision ID: 0001_initial_onyx_schema
Revises: 
Create Date: 2026-04-19 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_initial_onyx_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial schema with all tables, indexes, and views."""
    
    # ── Enums ────────────────────────────────────────────────────────
    session_status_enum = sa.Enum('created', 'recording', 'completed', 'archived', name='sessionstatus')
    calibration_state_enum = sa.Enum('not_started', 'in_progress', 'completed', name='calibrationstate')
    
    op.execute("CREATE TYPE sessionstatus AS ENUM ('created', 'recording', 'completed', 'archived')")
    op.execute("CREATE TYPE calibrationstate AS ENUM ('not_started', 'in_progress', 'completed')")
    
    # ── users table ──────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    
    # ── wearable_devices table ───────────────────────────────────────
    op.create_table(
        'wearable_devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('mac_address', sa.String(17), nullable=False, unique=True),
        sa.Column('firmware_version', sa.String(50)),
        sa.Column('last_seen', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mac_address', name='uq_devices_mac'),
    )
    op.create_index('ix_wearable_devices_user_id', 'wearable_devices', ['user_id'])
    
    # ── sessions table ───────────────────────────────────────────────
    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('status', session_status_enum, default='created'),
        sa.Column('calibration_state', calibration_state_enum, default='not_started'),
        sa.Column('court_corners', sa.JSON()),
        sa.Column('flash_residual_offset_ms', sa.Float()),
        sa.Column('session_start_utc_ms', sa.Float()),
        sa.Column('session_end_utc_ms', sa.Float()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['device_id'], ['wearable_devices.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
    op.create_index('ix_sessions_device_id', 'sessions', ['device_id'])
    
    # ── session_clock_syncs table ────────────────────────────────────
    op.create_table(
        'session_clock_syncs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('t1_device_ms', sa.Float(), nullable=False),
        sa.Column('t2_server_utc_ms', sa.Float(), nullable=False),
        sa.Column('t3_server_utc_ms', sa.Float(), nullable=False),
        sa.Column('t4_device_ms', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_session_clock_syncs_session_id', 'session_clock_syncs', ['session_id'])
    op.create_index('ix_session_clock_syncs_created_at', 'session_clock_syncs', ['created_at'])
    
    # ── session_videos table ─────────────────────────────────────────
    op.create_table(
        'session_videos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=False),
        sa.Column('fps', sa.Float()),
        sa.Column('frame_count', sa.Integer()),
        sa.Column('duration_seconds', sa.Float()),
        sa.Column('codec', sa.String(50)),
        sa.Column('encoding_status', sa.String(50), default='pending'),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_session_videos_session_id', 'session_videos', ['session_id'])
    op.create_index('ix_session_videos_created_at', 'session_videos', ['created_at'])
    
    # ── sensor_events table ──────────────────────────────────────────
    op.create_table(
        'sensor_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('device_ts_ms', sa.Float(), nullable=False),
        sa.Column('shot_type', sa.String(50)),
        sa.Column('confidence', sa.Float()),
        sa.Column('accel_x', sa.Float()),
        sa.Column('accel_y', sa.Float()),
        sa.Column('accel_z', sa.Float()),
        sa.Column('gyro_x', sa.Float()),
        sa.Column('gyro_y', sa.Float()),
        sa.Column('gyro_z', sa.Float()),
        sa.Column('euler_roll', sa.Float()),
        sa.Column('euler_pitch', sa.Float()),
        sa.Column('euler_yaw', sa.Float()),
        sa.Column('raw_data', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sensor_events_session_id', 'sensor_events', ['session_id'])
    op.create_index('ix_sensor_events_created_at_brin', 'sensor_events', ['created_at'], postgresql_using='brin')
    
    # ── video_frame_events table ─────────────────────────────────────
    op.create_table(
        'video_frame_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('video_id', sa.Integer()),
        sa.Column('frame_index', sa.Integer()),
        sa.Column('frame_utc_ms', sa.Float()),
        sa.Column('court_x_m', sa.Float()),
        sa.Column('court_y_m', sa.Float()),
        sa.Column('pose_keypoints', sa.JSON()),
        sa.Column('pose_quality', sa.Float()),
        sa.Column('person_count', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
        sa.ForeignKeyConstraint(['video_id'], ['session_videos.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_video_frame_events_session_id', 'video_frame_events', ['session_id'])
    op.create_index('ix_video_frame_events_frame_index', 'video_frame_events', ['frame_index'])
    op.create_index('ix_video_frame_events_created_at_brin', 'video_frame_events', ['created_at'], postgresql_using='brin')
    
    # ── fused_shots table ────────────────────────────────────────────
    op.create_table(
        'fused_shots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('sensor_event_id', sa.Integer(), unique=True),
        sa.Column('video_frame_event_id', sa.Integer()),
        sa.Column('shot_type', sa.String(50)),
        sa.Column('court_x_m', sa.Float()),
        sa.Column('court_y_m', sa.Float()),
        sa.Column('sensor_confidence', sa.Float()),
        sa.Column('vision_confidence', sa.Float()),
        sa.Column('fusion_confidence', sa.Float()),
        sa.Column('fusion_metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
        sa.ForeignKeyConstraint(['sensor_event_id'], ['sensor_events.id'], ),
        sa.ForeignKeyConstraint(['video_frame_event_id'], ['video_frame_events.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sensor_event_id', name='uq_fused_shots_sensor_event'),
    )
    op.create_index('ix_fused_shots_session_id', 'fused_shots', ['session_id'])
    op.create_index('ix_fused_shots_created_at_brin', 'fused_shots', ['created_at'], postgresql_using='brin')
    
    # ── View: v_session_overview ─────────────────────────────────────
    op.execute("""
        CREATE VIEW v_session_overview AS
        SELECT 
            s.id,
            s.user_id,
            s.device_id,
            s.status,
            COUNT(DISTINCT se.id) as shot_count,
            COUNT(DISTINCT se.id) as sensor_event_count,
            COUNT(DISTINCT sv.id) as video_count,
            MAX(sv.duration_seconds) as total_duration_seconds,
            s.created_at
        FROM sessions s
        LEFT JOIN sensor_events se ON s.id = se.session_id
        LEFT JOIN session_videos sv ON s.id = sv.session_id
        GROUP BY s.id, s.user_id, s.device_id, s.status, s.created_at
    """)


def downgrade() -> None:
    """Drop all tables and views."""
    op.execute("DROP VIEW IF EXISTS v_session_overview")
    op.drop_table('fused_shots')
    op.drop_table('video_frame_events')
    op.drop_table('sensor_events')
    op.drop_table('session_videos')
    op.drop_table('session_clock_syncs')
    op.drop_table('sessions')
    op.drop_table('wearable_devices')
    op.drop_table('users')
    op.execute("DROP TYPE IF EXISTS calibrationstate")
    op.execute("DROP TYPE IF EXISTS sessionstatus")
