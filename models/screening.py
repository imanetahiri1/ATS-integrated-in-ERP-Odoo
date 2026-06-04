# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PhoneScreening(models.Model):
    _name = 'softy.phone.screening'
    _description = 'Screening Téléphonique'
    _rec_name = 'candidate_name'

    # Informations générales
    _sql_constraints = [
        ('unique_applicant_screening', 'UNIQUE(applicant_id)', 
         'Un seul screening tséléphonique par candidature est autorisé!')
    ]
    candidate_name = fields.Char('Nom du candidat', required=True)
    position = fields.Char('Poste', required=True)
    evaluator = fields.Many2one('res.users', 'Évaluateur/Recruteur', default=lambda self: self.env.user, required=True)
    
    # Relation avec hr.applicant
    applicant_id = fields.Many2one('hr.applicant', 'Candidature', ondelete='cascade')
    
    # Date de l'appel
    call_date = fields.Date('Date de l\'appel', default=fields.Date.today, required=True)
    
    # Dernier poste occupé
    last_position = fields.Text('Dernier poste occupé')
    
    # Cumul d'expérience
    total_experience = fields.Integer('Cumul d\'expérience (années)')
    
    # Localisation
    location = fields.Text('Localisation')
    
    # Situation actuelle
    current_situation = fields.Selection([
        ('employed', 'En poste'),
        ('unemployed', 'Non en poste')
    ], 'Situation actuelle')
    
    # Disponibilité
    availability = fields.Selection([
        ('immediate', 'Immédiate'),
        ('1_month', '1 mois'),
        ('3_months', '3 mois'),
        ('to_agree', 'À convenir')
    ], 'Disponibilité')
    availability_details = fields.Text('Détails disponibilité')
    
    # Mobilité
    mobility = fields.Text('Mobilité')
    
    # Rémunération actuelle
    current_salary = fields.Text('Rémunération actuelle')
    
    # Prétentions salariales
    salary_expectations = fields.Text('Prétentions salariales')
    
    # Motivation au changement
    motivation_change = fields.Text('Motivation au changement')
    
    # Situation matrimoniale
    marital_status = fields.Selection([
        ('single', 'Célibataire'),
        ('married', 'Marié(e)'),
        ('divorced', 'Divorcé(e)'),
        ('widowed', 'Veuf/Veuve'),
        ('other', 'Autre')
    ], 'Situation matrimoniale')
    
    # Nombre d'enfants
    number_children = fields.Selection([
        ('0', '0'),
        ('1', '1'),
        ('2', '2'),
        ('3_plus', '3 +')
    ], 'Nombre d\'enfants')
    
    # CV à jour
    cv_updated = fields.Selection([
        ('yes', 'Oui'),
        ('no', 'Non')
    ], 'CV à jour')
    
    # Proposition d'entretien approfondi
    interview_proposal = fields.Selection([
        ('yes', 'Oui'),
        ('no', 'Non')
    ], 'Proposition d\'entretien approfondi')
    
    # Commentaire supplémentaire
    additional_comments = fields.Text('Commentaire supplémentaire')
    
    # Auto-populate candidate info from applicant
    @api.onchange('applicant_id')
    def _onchange_applicant_id(self):
        if self.applicant_id:
            self.candidate_name = self.applicant_id.partner_name
            self.position = self.applicant_id.job_id.name if self.applicant_id.job_id else ''
    
    def name_get(self):
        """Display name with candidate and call date"""
        result = []
        for record in self:
            call_date_str = record.call_date.strftime('%d/%m/%Y') if record.call_date else ''
            name = f"{record.candidate_name} - {call_date_str}"
            result.append((record.id, name))
        return result