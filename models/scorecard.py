# -*- coding: utf-8 -*-
from odoo import models, fields, api


class RecruitmentScorecard(models.Model):
    _name = 'softy.scorecard'
    _description = 'Scorecard de Recrutement'
    _rec_name = 'candidate_name'

    # Informations générales
    _sql_constraints = [
        ('unique_applicant_scorecard', 'UNIQUE(applicant_id)', 
         'Un seul scorecard par candidature est autorisé!')
    ]
    candidate_name = fields.Char('Nom du candidat', required=True)
    position = fields.Char('Poste', required=True)
    evaluation_date = fields.Date("Date", default=fields.Date.today, required=True)
    evaluator = fields.Many2one('res.users', 'Évaluateur/Recruteur', default=lambda self: self.env.user, required=True)
    
    # Relation avec hr.applicant
    applicant_id = fields.Many2one('hr.applicant', 'Candidature', ondelete='cascade')
    
    # 1. Présentation du CV (0-1 points)
    cv_presentation = fields.Selection([
        ('1', 'CV clair, bien structuré, cohérent, sans fautes majeures et crédible'),
        ('0', 'CV confus, mal structuré, fautes importantes ou douteux')
    ], 'Présentation du CV', required=True)
    cv_presentation_score = fields.Integer('Score CV', compute='_compute_cv_presentation_score', store=True)
    cv_presentation_justification = fields.Text('Justification')
    
    # 2. Diplôme et qualifications (0-3 points)
    diploma_level = fields.Selection([
        ('3', 'Diplôme parfaitement aligné avec le poste demandé'),
        ('2', 'Diplôme connexe mais cohérent'),
        ('1', 'Diplôme éloigné'),
        ('0', 'Hors périmètre')
    ], 'Diplôme et qualifications', required=True)
    diploma_score = fields.Integer('Score Diplôme', compute='_compute_diploma_score', store=True)
    diploma_justification = fields.Text('Justification')
    
    # 3. Expérience professionnelle (0-2 points)
    experience_level = fields.Selection([
        ('2', 'Expérience confirmée et directement alignée avec le poste'),
        ('1', 'Expérience partielle ou non approfondie'),
        ('0', 'Expérience non maîtrisée ou non pertinente')
    ], 'Expérience professionnelle', required=True)
    experience_score = fields.Integer('Score Expérience', compute='_compute_experience_score', store=True)
    experience_justification = fields.Text('Justification')
    
    # 4. Compétences métier (0-3 points)
    job_skills = fields.Selection([
        ('3', 'Maîtrise démontrée des outils/techniques requis'),
        ('2', 'Bonnes bases, mais à renforcer'),
        ('1', 'Notions insuffisantes'),
        ('0', 'Compétences absentes')
    ], 'Compétences métier', required=True)
    job_skills_score = fields.Integer('Score Compétences', compute='_compute_job_skills_score', store=True)
    job_skills_justification = fields.Text('Justification')
    
    # 5. Soft skills (0-3 points)
    soft_skills = fields.Selection([
        ('3', 'Communication fluide, bonne posture, soft skills en adéquation avec le poste'),
        ('2', 'Acceptables mais à renforcer'),
        ('1', 'Fragiles ou peu visibles'),
        ('0', 'Inadaptés au poste')
    ], 'Soft skills (communication, leadership, équipe)', required=True)
    soft_skills_score = fields.Integer('Score Soft Skills', compute='_compute_soft_skills_score', store=True)
    soft_skills_justification = fields.Text('Justification')
    
    # 6. Maîtrise des langues (0-2 points)
    language_skills = fields.Selection([
        ('2', 'Niveau requis maîtrisé (oral et écrit)'),
        ('1', 'Niveau insuffisant mais améliorable'),
        ('0', 'Inadéquat ou non conforme à l\'exigence')
    ], 'Maîtrise des langues (Français/Anglais)', required=True)
    language_score = fields.Integer('Score Langues', compute='_compute_language_score', store=True)
    language_justification = fields.Text('Justification')
    
    # 7. Tranche d'âge (0-1 points)
    age_range = fields.Selection([
        ('1', 'Tranche d\'âge correspondant à la cible définie par le client'),
        ('0', 'Hors cible')
    ], 'Tranche d\'âge', required=True)
    age_score = fields.Integer('Score Âge', compute='_compute_age_score', store=True)
    age_justification = fields.Text('Justification')
    
    # 8. Mobilité/Localisation (0-2 points)
    mobility = fields.Selection([
        ('2', 'Réside dans une zone prioritaire définie par le client'),
        ('1', 'Réside dans la même ville mais hors zone prioritaire'),
        ('0', 'Réside hors de la ville concernée ou refuse la mobilité requise')
    ], 'Mobilité/Localisation', required=True)
    mobility_score = fields.Integer('Score Mobilité', compute='_compute_mobility_score', store=True)
    mobility_justification = fields.Text('Justification')
    
    # 9. Motivation et engagement (0-2 points)
    motivation = fields.Selection([
        ('2', 'Projet clair, motivation forte, cohérence du parcours'),
        ('1', 'Motivation moyenne, hésitations'),
        ('0', 'Motivation absente ou instable')
    ], 'Motivation et engagement', required=True)
    motivation_score = fields.Integer('Score Motivation', compute='_compute_motivation_score', store=True)
    motivation_justification = fields.Text('Justification')
    
    # 10. Prétention Salariale (0-1 points)
    salary_expectation = fields.Selection([
        ('1', 'Conforme au budget client ou légèrement négociable'),
        ('0', 'Hors budget et non négociable')
    ], 'Prétention Salariale', required=True)
    salary_expectation_score = fields.Integer('Score Prétention', compute='_compute_salary_expectation_score', store=True)
    salary_expectation_justification = fields.Text('Justification')
    
    # Scores et totaux
    total_score = fields.Integer('Total points', compute='_compute_total_score', store=True)
    max_score = fields.Integer('Score Maximum', default=20, readonly=True)
    
    # Seuil recommandé
    threshold_met = fields.Boolean('Seuil atteint', compute='_compute_threshold_met', store=True)
    decision = fields.Selection([
        ('selected', 'Retenu/Sélectionné'),
        ('rejected', 'Refusé/Rejeté')
    ], 'Décision', compute='_compute_decision', store=True)
    
    # Auto-populate candidate info from applicant
    @api.onchange('applicant_id')
    def _onchange_applicant_id(self):
        if self.applicant_id:
            self.candidate_name = self.applicant_id.partner_name
            self.position = self.applicant_id.job_id.name if self.applicant_id.job_id else ''
    
    # Computed methods for automatic scoring
    @api.depends('cv_presentation')
    def _compute_cv_presentation_score(self):
        for record in self:
            record.cv_presentation_score = int(record.cv_presentation) if record.cv_presentation else 0
    
    @api.depends('diploma_level')
    def _compute_diploma_score(self):
        for record in self:
            record.diploma_score = int(record.diploma_level) if record.diploma_level else 0
    
    @api.depends('experience_level')
    def _compute_experience_score(self):
        for record in self:
            record.experience_score = int(record.experience_level) if record.experience_level else 0
    
    @api.depends('job_skills')
    def _compute_job_skills_score(self):
        for record in self:
            record.job_skills_score = int(record.job_skills) if record.job_skills else 0
    
    @api.depends('soft_skills')
    def _compute_soft_skills_score(self):
        for record in self:
            record.soft_skills_score = int(record.soft_skills) if record.soft_skills else 0
    
    @api.depends('language_skills')
    def _compute_language_score(self):
        for record in self:
            record.language_score = int(record.language_skills) if record.language_skills else 0
    
    @api.depends('age_range')
    def _compute_age_score(self):
        for record in self:
            record.age_score = int(record.age_range) if record.age_range else 0
    
    @api.depends('mobility')
    def _compute_mobility_score(self):
        for record in self:
            record.mobility_score = int(record.mobility) if record.mobility else 0
    
    @api.depends('motivation')
    def _compute_motivation_score(self):
        for record in self:
            record.motivation_score = int(record.motivation) if record.motivation else 0
    
    @api.depends('salary_expectation')
    def _compute_salary_expectation_score(self):
        for record in self:
            record.salary_expectation_score = int(record.salary_expectation) if record.salary_expectation else 0
    
    @api.depends('cv_presentation_score', 'diploma_score', 'experience_score', 'job_skills_score',
                 'soft_skills_score', 'language_score', 'age_score', 'mobility_score',
                 'motivation_score', 'salary_expectation_score')
    def _compute_total_score(self):
        for record in self:
            record.total_score = (
                record.cv_presentation_score + record.diploma_score + record.experience_score +
                record.job_skills_score + record.soft_skills_score + record.language_score +
                record.age_score + record.mobility_score + record.motivation_score +
                record.salary_expectation_score
            )
    
    @api.depends('total_score')
    def _compute_threshold_met(self):
        for record in self:
            record.threshold_met = record.total_score >= 10
    
    @api.depends('total_score')
    def _compute_decision(self):
        for record in self:
            if record.total_score >= 10:
                record.decision = 'selected'
            else:
                record.decision = 'rejected'

    def name_get(self):
        """Display name with candidate and score"""
        result = []
        for record in self:
            name = f"{record.candidate_name} ({record.total_score}/20)"
            result.append((record.id, name))
        return result