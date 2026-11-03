"""Initial empty baseline

Revision ID: 0001
Revises: None
Create Date: 2026-11-02 21:04:02.303464

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Establish the baseline without creating domain tables."""
    pass


def downgrade() -> None:
    """No domain schema changes to undo."""
    pass
