"""GN permission 2.13

Revision ID: e27e2994d3bd
Revises: 42732da3363e
Create Date: 2023-08-11 12:22:46.425506
"""
from alembic import op
import sqlalchemy as sa

revision = "e27e2994d3bd"
down_revision = "42732da3363e"
branch_labels = None
depends_on = None


def upgrade():

    # 1) Créer l'objet PARSER si pas déjà présent
    op.execute("""
        INSERT INTO gn_permissions.t_objects (code_object, description_object)
        SELECT 'PARSER', 'Gestion des parser dans le backoffice'
        WHERE NOT EXISTS (
            SELECT 1 FROM gn_permissions.t_objects WHERE code_object = 'PARSER'
        );
    """)

    # 2) Créer le module API2GN seulement s'il n'existe pas
    op.execute("""
        INSERT INTO gn_commons.t_modules
        (module_code, module_label, module_desc, module_external_url, active_frontend, active_backend)
        SELECT 'API2GN', 'Api2GN', 'Module API2GN', '_blank', false, false
        WHERE NOT EXISTS (
            SELECT 1 FROM gn_commons.t_modules WHERE module_code = 'API2GN'
        );
    """)

    # 3) Créer les permissions sans doublon
    op.execute("""
        INSERT INTO gn_permissions.t_permissions_available (
            id_module, id_object, id_action, scope_filter, label
        )
        SELECT
            m.id_module,
            o.id_object,
            a.id_action,
            v.scope_filter,
            v.label
        FROM (
            VALUES
                ('API2GN', 'PARSER', 'R', False, 'Voir les parsers'),
                ('API2GN', 'PARSER', 'U', False, 'Modifier les parser'),
                ('API2GN', 'PARSER', 'C', False, 'Créer des parser'),
                ('API2GN', 'PARSER', 'D', False, 'Supprimer des parsers')
        ) AS v (module_code, object_code, action_code, scope_filter, label)
        JOIN gn_commons.t_modules m ON m.module_code = v.module_code
        JOIN gn_permissions.t_objects o ON o.code_object = v.object_code
        JOIN gn_permissions.bib_actions a ON a.code_action = v.action_code
        WHERE NOT EXISTS (
            SELECT 1 FROM gn_permissions.t_permissions_available pa
            WHERE pa.id_module = m.id_module
            AND pa.id_object = o.id_object
            AND pa.id_action = a.id_action
        );
    """)


def downgrade():
    op.execute("""
        DELETE FROM gn_permissions.t_permissions_available
        WHERE id_object = (SELECT id_object FROM gn_permissions.t_objects WHERE code_object = 'PARSER');

        DELETE FROM gn_permissions.t_objects WHERE code_object = 'PARSER';

        DELETE FROM gn_commons.t_modules WHERE module_code = 'API2GN';
    """)
