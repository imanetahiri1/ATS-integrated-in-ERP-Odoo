# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SmartOffre(models.Model):
    _name = "smart.offre"
    _description = "Offre d'emploi Smart Recruitment"
    _rec_name = 'name'

    name = fields.Char(string="Titre du poste", required=True)

    # Description style Vettio
    description = fields.Html(
        string="Description du poste",
        help="Décrivez le poste en détail (contexte, missions, environnement...)"
    )
    profil_recherche = fields.Html(
        string="Profil recherché",
        help="Décrivez le candidat idéal (soft skills, personnalité, motivations...)"
    )
    competences_requises = fields.Text(
        string="Compétences requises",
        help="Ex: Python, Odoo, SQL, Machine Learning..."
    )
    competences_bonus = fields.Text(
        string="Compétences bonus (nice to have)",
        help="Compétences appréciées mais non obligatoires"
    )
    criteres_obligatoires = fields.Text(
        string="Critères non-négociables",
        help="Maximum 5 critères — si absent chez le candidat → rejet automatique"
    )
    criteres_autres = fields.Text(
        string="Autres critères d'évaluation",
        help="Critères importants mais non éliminatoires"
    )
    reference_externe = fields.Char(
        string="ID Offre (MarocAnnonce / SharePoint)",
        help="Identifiant unique utilisé dans MarocAnnonce et SharePoint"
    )
    nb_shortlist = fields.Integer(
        string="Nombre de candidats à shortlister",
        default=20,
        help="Top N candidats à shortlister automatiquement"
    )
    experience_min = fields.Integer(
        string="Expérience minimum (années)",
        default=0
    )
    niveau_formation = fields.Selection([
        ('bac', 'Bac'),
        ('bac2', 'Bac+2'),
        ('bac3', 'Bac+3'),
        ('bac5', 'Bac+5'),
        ('doctorat', 'Doctorat'),
        ('any', 'Peu importe'),
    ], string="Niveau de formation requis", default='any')

    localisation = fields.Char(string="Localisation / Ville")
    type_contrat = fields.Selection([
        ('cdi', 'CDI'),
        ('cdd', 'CDD'),
        ('stage', 'Stage'),
        ('alternance', 'Alternance'),
        ('freelance', 'Freelance'),
    ], string="Type de contrat", default='cdi')

    # Statut
    state = fields.Selection([
        ('open', 'Ouvert'),
        ('closed', 'Fermé'),
    ], string="Statut", default='open')

    # Relation candidats
    candidat_ids = fields.One2many(
        'smart.candidat', 'job_id',
        string="Candidats"
    )
    candidat_count = fields.Integer(
        string="Nombre de candidats",
        compute='_compute_candidat_count',
        store=False
    )
    secteur_activite = fields.Char(
        string="Secteur d'activité",
        help="Ex: Finance, Industrie, IT, Commerce..."
    )

    # CHAMPS RTP (Alignement avec le système RTP externe)
    affaire_numero = fields.Char(
        string="Affaire N°",
        help="Numéro de l'affaire dans le système RTP"
    )
    client_demandeur = fields.Char(
        string="Client / Demandeur",
        help="Nom du client ou du demandeur de recrutement"
    )
    motif_recrutement = fields.Selection([
        ('remplacement', 'Remplacement'),
        ('creation_poste', 'Création de poste'),
        ('surcroit_activite', 'Surcroît d\'activité'),
        ('projet', 'Projet temporaire'),
        ('autre', 'Autre'),
    ], string="Motif de recrutement")
    
    budget_poste = fields.Char(
        string="Budget du poste",
        help="Ex: 15 000 - 20 000 MAD/mois"
    )
    date_prevue_demarrage = fields.Date(
        string="Date prévue de démarrage"
    )
    age_souhaite = fields.Char(
        string="Âge souhaité",
        help="Ex: 25-35 ans, 30 ans minimum..."
    )
    sexe_souhaite = fields.Selection([
        ('homme', 'Homme'),
        ('femme', 'Femme'),
        ('indifferent', 'Indifférent'),
    ], string="Sexe souhaité", default='indifferent')
    
    missions_taches = fields.Text(
        string="Missions et tâches globales",
        help="Description détaillée des missions principales du poste"
    )
    qualites_personnelles = fields.Text(
        string="Qualités personnelles",
        help="Soft skills et qualités humaines recherchées"
    )
    connaissances_specifiques = fields.Text(
        string="Connaissances spécifiques",
        help="Connaissances techniques, logiciels, certifications..."
    )
    autres_avantages = fields.Text(
        string="Autres avantages",
        help="Avantages sociaux, primes, avantages en nature..."
    )

    job_id = fields.Many2one(
        'hr.job',
        string="Poste Odoo lié",
        ondelete='set null',
        help="Lien bidirectionnel vers le poste dans le module RH natif"
    )

    # === PONDÉRATIONS PERSONNALISÉES (SCORING) ===
    poids_competences = fields.Float(
        string="Poids Compétences", 
        default=20.0,
        help="Pondération du score des compétences"
    )
    poids_experience = fields.Float(
        string="Poids Expérience", 
        default=30.0,
        help="Pondération du score de l'expérience"
    )
    poids_formation = fields.Float(
        string="Poids Formation", 
        default=20.0,
        help="Pondération du score de la formation"
    )
    poids_geo = fields.Float(
        string="Poids Géolocalisation", 
        default=10.0,
        help="Pondération du score de proximité géographique"
    )
    poids_gemini = fields.Float(
        string="Poids Analyse Gemini", 
        default=20.0,
        help="Pondération du score de l'analyse IA Gemini"
    )

    # === SEUILS DE DÉCISION AUTOMATIQUE ===
    seuil_shortlist = fields.Float(
        string="Seuil Shortlist (>= X/100)", 
        default=70.0,
        help="Score minimum pour shortlister automatiquement un candidat"
    )
    seuil_rejet = fields.Float(
        string="Seuil Rejet (< X/100)", 
        default=50.0,
        help="Score maximum pour rejeter automatiquement un candidat"
    )

    # === CONTRAINTES DE VALIDATION ===
    @api.constrains('poids_competences', 'poids_experience', 'poids_formation', 
                    'poids_geo', 'poids_gemini')
    def _check_poids_total(self):
        """Vérifier que le total des poids = 100"""
        for offre in self:
            total = (offre.poids_competences + offre.poids_experience + 
                    offre.poids_formation + offre.poids_geo + offre.poids_gemini)
            if abs(total - 100.0) > 0.1:  # tolérance de 0.1
                raise ValidationError(
                    f"Le total des pondérations doit être égal à 100. "
                    f"Total actuel : {total:.1f}"
                )

    @api.constrains('seuil_shortlist', 'seuil_rejet')
    def _check_seuils(self):
        """Vérifier que seuil_shortlist > seuil_rejet"""
        for offre in self:
            if offre.seuil_shortlist <= offre.seuil_rejet:
                raise ValidationError(
                    "Le seuil de shortlist doit être supérieur au seuil de rejet"
                )
        
    def write(self, vals):
        """
        Si les seuils changent, redéplacer automatiquement
        tous les candidats scorés dans le bon Kanban.
        """
        res = super(SmartOffre, self).write(vals)
        
        if 'seuil_shortlist' in vals or 'seuil_rejet' in vals:
            for offre in self:
                candidats_scores = self.env['smart.candidat'].search([
                    ('job_id', '=', offre.id),
                    ('ai_score', '>', 0),
                ])
                
                for candidat in candidats_scores:
                    score = candidat.ai_score
                    seuil_shortlist = offre.seuil_shortlist
                    seuil_rejet = offre.seuil_rejet
                    
                    if score >= seuil_shortlist:
                        candidat.write({
                            'state': 'shortlisted',
                            'shortlisted': True,
                        })
                    elif score < seuil_rejet:
                        candidat.write({
                            'state': 'rejected',
                            'shortlisted': False,
                        })
                    else:
                        candidat.write({
                            'state': 'analyzed',
                            'shortlisted': False,
                        })
                    
                    try:
                        candidat._move_to_kanban_stage()
                    except Exception as e:
                        _logger.warning(
                            "Redéplacement Kanban échoué pour %s: %s",
                            candidat.name, str(e)
                        )
        self.env.cr.commit()
        return res
    

    @api.depends('candidat_ids')
    def _compute_candidat_count(self):
        for rec in self:
            rec.candidat_count = len(rec.candidat_ids)

    def action_voir_candidats(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Candidats — {self.name}',
            'res_model': 'smart.candidat',
            'view_mode': 'list,form',
            'domain': [('job_id', '=', self.id)],
            'context': {'default_job_id': self.id},
        }

    def action_scorer_tous_candidats(self):
        """
        Lance le scoring en 2 passes (si Gemini activé) :
        - PHASE 1 : Scoring Python sur TOUS les candidats
        - PHASE 2 : Scoring Gemini UNIQUEMENT si poids_gemini > 0
        
        PHASE B : Optimisé avec prefetch pour éviter N+1
        """
        if not self.candidat_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Aucun candidat',
                    'message': 'Cette offre n\'a pas encore de candidats.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # PHASE B : OPTIMISATION - Prefetch pour éviter N+1
        candidats_a_scorer = self.env['smart.candidat'].search(
            [('job_id', '=', self.id)]
        ).with_context(prefetch_fields=['job_id', 'cv_text', 'state'])
        
        nb_total = len(candidats_a_scorer)
        
        _logger.info(
            "=== PHASE 1 : Scoring Python sur %s candidats ===",
            nb_total
        )
        
        for candidat in candidats_a_scorer:
            try:
                candidat.calculer_score_python_seulement()
            except Exception as e:
                _logger.warning(
                    "Scoring Python échoué pour %s: %s",
                    candidat.name, str(e)
                )
        
        # VÉRIFIER SI GEMINI EST ACTIVÉ
        poids_gemini = self.poids_gemini if self.poids_gemini is not False else 0.0
        
        if poids_gemini == 0:
            _logger.info(
                "=== Gemini désactivé (poids=0) - Scoring Python uniquement ==="
            )
            self._recompute_ranks()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Scoring Python terminé',
                    'message': f'{nb_total} candidat(s) scorés par Python (Gemini désactivé).',
                    'type': 'success',
                    'sticky': True,
                }
            }
        
        # PHASE 2 : Identifier les candidats SHORTLISTÉS pour Gemini
        # PHASE B : OPTIMISATION - Prefetch
        candidats_shortlistes = self.env['smart.candidat'].search(
            [
                ('job_id', '=', self.id),
                ('state', '=', 'shortlisted'),
            ]
        ).with_context(prefetch_fields=['job_id', 'cv_text', 'state'])
        
        nb_shortlistes = len(candidats_shortlistes)
        
        if nb_shortlistes == 0:
            _logger.info(
                "=== Aucun candidat shortlisté pour scoring Gemini ==="
            )
            self._recompute_ranks()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Scoring Python terminé',
                    'message': (
                        f'{nb_total} candidat(s) scorés par Python (/80).\n'
                        f'Aucun candidat shortlisté pour scoring Gemini.'
                    ),
                    'type': 'info',
                    'sticky': True,
                }
            }
        
        _logger.info(
            "=== PHASE 2 : Scoring Gemini sur %s candidats shortlistés ===",
            nb_shortlistes
        )
        
        # PHASE 3 : Scoring Gemini sur les candidats shortlistés
        nb_gemini_reussi = 0
        for candidat in candidats_shortlistes:
            try:
                candidat.action_analyser_cv()
                nb_gemini_reussi += 1
            except Exception as e:
                _logger.warning(
                    "Scoring Gemini échoué pour %s: %s",
                    candidat.name, str(e)
                )
        
        # Recalcul des rangs
        self._recompute_ranks()
        
        # Notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Scoring 2-passes terminé',
                'message': (
                    f'Phase 1 : {nb_total} candidat(s) scorés par Python\n'
                    f'Phase 2 : {nb_gemini_reussi}/{nb_shortlistes} candidat(s) analysés par Gemini'
                ),
                'type': 'success',
                'sticky': True,
            }
        }

    def _recompute_ranks(self):
        """
        Recalcule le classement de tous les candidats de cette offre.
        PHASE B : Optimisé pour éviter les requêtes N+1.
        """
        # OPTIMISATION : 1 seule requête SQL au lieu de N
        candidats = self.env['smart.candidat'].search(
            [('job_id', '=', self.id)],
            order='ai_score desc, id desc'
        )
        
        # Batch update pour éviter N écritures séparées
        vals_list = []
        for idx, candidat in enumerate(candidats):
            vals_list.append({
                'id': candidat.id,
                'ai_rank': idx + 1
            })
        
        # 1 seule requête SQL pour tous les updates
        if vals_list:
            self.env.cr.execute("""
                UPDATE smart_candidat AS c
                SET ai_rank = v.rank
                FROM (VALUES %s) AS v(id, rank)
                WHERE c.id = v.id
            """ % ','.join(
                f"({v['id']},{v['ai_rank']})" for v in vals_list
            ))
            self.env.cr.commit()
            
            _logger.debug(
                "✅ Rangs recalculés pour %d candidats (offre %s)",
                len(vals_list), self.name
            )

    def _move_candidats_to_kanban(self):
        """
        Déplace automatiquement les candidats dans le Kanban softy_recrutement.
        PHASE B : Optimisé avec prefetch.
        """
        stage_shortlist = self.env['hr.recruitment.stage'].sudo().search(
            [('name', '=', 'CVs shortlistés')], limit=1
        )
        stage_rejete = self.env['hr.recruitment.stage'].sudo().search(
            [('name', '=', 'CVs présélectionnés')], limit=1
        )
        if not stage_shortlist or not stage_rejete:
            return

        # PHASE B : OPTIMISATION - Prefetch
        candidats_tries = self.env['smart.candidat'].search(
            [('job_id', '=', self.id)],
            order='ai_score desc'
        ).with_context(prefetch_fields=['email', 'ai_score'])
        
        top_n = self.nb_shortlist or 20

        for idx, candidat in enumerate(candidats_tries):
            if not candidat.email:
                continue
            applicant = self.env['hr.applicant'].sudo().search(
                [('email_from', '=', candidat.email)], limit=1
            )
            if not applicant:
                continue
            if idx < top_n:
                applicant.write({'stage_id': stage_shortlist.id})
            else:
                applicant.write({'stage_id': stage_rejete.id})