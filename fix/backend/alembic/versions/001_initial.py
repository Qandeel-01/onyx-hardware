"""Initial migration: create sessions, shot_events, clock_calibrations, video_segments tables.

Revision ID: 001_initial
Revises: 
Create Date: 2026-04-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from uuid import uuid4

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.Column('player_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('video_file_path', sa.Text(), nullable=True),
        sa.Column('fps', sa.Float(), nullable=False, server_default='30.0'),
        sa.Column('sync_quality', sa.String(50), nullable=False, server_default='none'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # Create clock_calibrations table
    op.create_table(
        'clock_calibrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('calibrated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('rtt_ms', sa.Float(), nullable=False),
        sa.Column('offset_ms', sa.Float(), nullable=False),
        sa.Column('quality', sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clock_calibrations_session_id'), 'clock_calibrations', ['session_id'])

    # Create shot_events table
    op.create_table(
        'shot_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('shot_type', sa.String(50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('device_ts_ms', sa.BigInteger(), nullable=False),
        sa.Column('wall_clock_ts', sa.DateTime(timezone=True), nullable=True),
        sa.Column('frame_index', sa.Integer(), nullable=True),
        sa.Column('accel_x', sa.Float(), nullable=True),
        sa.Column('accel_y', sa.Float(), nullable=True),
        sa.Column('accel_z', sa.Float(), nullable=True),
        sa.Column('gyro_x', sa.Float(), nullable=True),
        sa.Column('gyro_y', sa.Float(), nullable=True),
        sa.Column('gyro_z', sa.Float(), nullable=True),
        sa.Column('court_x', sa.Float(), nullable=True),
        sa.Column('court_y', sa.Float(), nullable=True),
        sa.Column('player_bbox', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('pose_keypoints', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_shot_events_session_id'), 'shot_events', ['session_id'])
    op.create_index(op.f('ix_shot_events_device_ts_ms'), 'shot_events', ['device_ts_ms'])

    # Create video_segments table
    op.create_table(
        'video_segments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('start_frame', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('end_frame', sa.Integer(), nullable=True),
        sa.Column('capture_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_video_segments_session_id'), 'video_segments', ['session_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_video_segments_session_id'), table_name='video_segments')
    op.drop_table('video_segments')
    op.drop_index(op.f('ix_shot_events_device_ts_ms'), table_name='shot_events')
    op.drop_index(op.f('ix_shot_events_session_id'), table_name='shot_events')
    op.drop_table('shot_events')
    op.drop_index(op.f('ix_clock_calibrations_session_id'), table_name='clock_calibrations')
    op.drop_table('clock_calibrations')
    op.drop_table('sessions')
