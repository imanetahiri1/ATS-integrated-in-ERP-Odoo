from email.policy import default
from odoo import api, fields, models, _
from datetime import date

class HrJobInherit(models.Model):
    _inherit = 'hr.job'
    
    status = fields.Selection(
        [
            ("en_cours", "En cours"),
            ("annule", "Annulé"),
            ("cloture", "Clôturé"),
            ("non_comm","Non Commencé"),
            ("retour","En Attente Retour du Client")
        ],
        string=_("Statut du suivi"),
        help=("État d'avancement du recrutement"),
        default="en_cours",
        required=False
    )
    dateenvoi1=fields.Date(string="Premier Date d'envoie")
    nbrenvoie1=fields.Integer(string="Nombre de CV Envoyé / Premier vague")
    dateenvoi2=fields.Date(string="Deuxieme Date d'envoie")
    nbrenvoie2=fields.Integer(string="Nombre de CV Envoyé / Deuxieme vague")
    dateenvoi3=fields.Date(string="Troisieme Date d'envoie")
    nbrenvoie3=fields.Integer(string="Nombre de CV Envoyé / Troisieme vague")
    
    # Champ calculé pour les jours restants
    jours_restants = fields.Integer(
        string="Jours restants",
        compute="_compute_jours_restants",
        store=False
    )
    
    @api.depends('date_to')
    def _compute_jours_restants(self):
        today = date.today()
        for record in self:
            if record.date_to:
                delta = (record.date_to - today).days
                record.jours_restants = delta
            else:
                record.jours_restants = 0
    
    # Document requirements for administrative validation
    copy_cin = fields.Boolean(
        string="2 copies de la CIN légalisées & attestation CNSS",
        help="Document requis pour la validation administrative",
    )
    doc_cv = fields.Boolean(
        string="Curriculum Vitae (CV)",
        help="Document requis pour la validation administrative",
    )
    doc_diplomes = fields.Boolean(
        string="Copies légalisées des diplômes",
        help="Document requis pour la validation administrative",
    )
    doc_demission = fields.Boolean(
        string="Copie légalisée de la démission",
        help="Document requis pour la validation administrative",
    )
    doc_bulletins_paie = fields.Boolean(
        string="3 derniers bulletins de paie cachetés",
        help="Document requis pour la validation administrative",
    )
    doc_attestation_libre = fields.Boolean(
        string="Attestation de travail précisant que vous êtes libre de tout engagement",
        help="Document requis pour la validation administrative",
    )
    doc_certificats_travail = fields.Boolean(
        string="Certificats de travail",
        help="Document requis pour la validation administrative",
    )
    doc_rib = fields.Boolean(
        string="RIB ou attestation bancaire",
        help="Document requis pour la validation administrative",
    )
    doc_acte_mariage = fields.Boolean(
        string="Acte de mariage + copie CIN de l'époux(se) (si marié(e))",
        help="Document requis pour la validation administrative",
    )
    doc_extraits_naissance = fields.Boolean(
        string="Extrait(s) de naissance des enfants (le cas échéant)",
        help="Document requis pour la validation administrative",
    )
    doc_anthropometrique = fields.Boolean(
        string="Fiche anthropométrique récente",
        help="Document requis pour la validation administrative",
    )
    doc_radiologie = fields.Boolean(
        string="Radio pulmonaire",
        help="Document requis pour la validation administrative",
    )
    # ═══════════════════════════════════════════
    # CHAMPS IA (fusionnés depuis smart.offre)
    # ═══════════════════════════════════════════
    
    # Lien vers l'offre IA correspondante
    offre_ia_id = fields.Many2one(
        'smart.offre',
        string="Offre IA liée",
        help="Offre IA associée à ce poste pour le scoring"
    )
    
    # Critères IA
    competences_requises = fields.Text(
        string="Compétences requises",
        help="Ex: Python, Odoo, SQL..."
    )
    competences_bonus = fields.Text(
        string="Compétences bonus",
        help="Compétences appréciées mais non obligatoires"
    )
    criteres_obligatoires = fields.Text(
        string="Critères non-négociables",
        help="Maximum 5 critères — absence = rejet automatique"
    )
    criteres_autres = fields.Text(
        string="Autres critères d'évaluation"
    )
    experience_min = fields.Integer(
        string="Expérience minimum (années)",
        default=0
    )
    niveau_formation_requis = fields.Selection([
        ('bac', 'Bac'),
        ('bac2', 'Bac+2'),
        ('bac3', 'Bac+3'),
        ('bac5', 'Bac+5'),
        ('doctorat', 'Doctorat'),
        ('any', 'Peu importe'),
    ], string="Niveau de formation requis", default='any')
    nb_shortlist = fields.Integer(
        string="Nombre de candidats à shortlister (Top N)",
        default=20
    )
    score_minimum = fields.Float(
    string="Score minimum (/100)",
    default=50.0,
    help="Indicateur visuel : score en dessous duquel un candidat est considéré faible"
    )
    localisation = fields.Char(string="Localisation / Ville")
    secteur_activite = fields.Char(string="Secteur d'activité")

    # Informations RTP
    reference_externe = fields.Char(string="ID Offre RTP")
    affaire_numero = fields.Char(string="Affaire N°")
    client_demandeur = fields.Char(string="Client / Demandeur")
    motif_recrutement = fields.Selection([
        ('remplacement', 'Remplacement'),
        ('creation_poste', 'Création de poste'),
        ('surcroit_activite', "Surcroît d'activité"),
        ('projet', 'Projet temporaire'),
        ('autre', 'Autre'),
    ], string="Motif de recrutement")
    budget_poste = fields.Char(string="Budget du poste")
    date_prevue_demarrage = fields.Date(string="Date prévue de démarrage")
    age_souhaite = fields.Char(string="Âge souhaité")
    sexe_souhaite = fields.Selection([
        ('homme', 'Homme'),
        ('femme', 'Femme'),
        ('indifferent', 'Indifférent'),
    ], string="Sexe souhaité", default='indifferent')
    missions_taches = fields.Text(string="Missions et tâches")
    qualites_personnelles = fields.Text(string="Qualités personnelles")
    connaissances_specifiques = fields.Text(string="Connaissances spécifiques")
    autres_avantages = fields.Text(string="Autres avantages")

    # ═══════════════════════════════════════════
    # MÉTHODES IA
    # ═══════════════════════════════════════════

    def action_scorer_tous_candidats(self):
        """Délègue le scoring à l'offre IA liée."""
        if self.offre_ia_id:
            return self.offre_ia_id.action_scorer_tous_candidats()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Aucune offre IA liée',
                'message': 'Liez ce poste à une offre IA dans l\'onglet "Critères IA".',
                'type': 'warning',
            }
        }

    def action_importer_cvs(self):
        """Ouvre le wizard d'import de CVs."""
        if self.offre_ia_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'smart.import.batch.cv.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_offre_id': self.offre_ia_id.id},
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Aucune offre IA liée',
                'message': 'Liez ce poste à une offre IA d\'abord.',
                'type': 'warning',
            }
        }