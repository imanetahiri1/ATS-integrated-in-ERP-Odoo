{
    'name': 'Softy Recruitment',
    'version': '18.0.1.0.1',
    'category': 'Human Resources',
    'summary': 'Extension for Odoo Recruitment Module',
    'description': """
        Softy Recrutement - Système de recrutement intelligent avec IA
    """,
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr_recruitment',
        'hr',
        'website_hr_recruitment',
        'hr_skills',
        
    ],
    'assets': {
        'web.assets_frontend': [
            'softy_recrutement/static/src/css/custom_styles.css',
        ],
        'web.assets_backend': [
            'softy_recrutement/static/src/js/cv_preview_widget.js',
        ],
    },
    'data': [
        # 1. D'ABORD : Données de base
        'data/mails.xml',
        'data/cron.xml',
        
        # 2. ENSUITE : Toutes les vues (qui créent les modèles dans la DB)
        'views/smart_candidat_views.xml',
        'views/import_batch_wizard_views.xml',
        'views/offre_views.xml',
        'views/menu_views.xml',
        'views/doc_views.xml',
        'views/candidate_views.xml',
        'views/jobs.xml',
        'views/dep.xml',
        'views/candidature_views.xml',
        'views/recruitment_candidate_list_views.xml',
        'views/recruitment_candidate_batch_views.xml',
        'views/website_hr_recruitment_templates.xml',
        'views/job_offers_extension.xml',
        
        # 3. EN DERNIER : Les droits d'accès (après que les modèles existent)
        'security/ir.model.access.csv',
    ],

    'installable': True,
    'auto_install': False,
    'application': False,
    'sequence': 100,
}
