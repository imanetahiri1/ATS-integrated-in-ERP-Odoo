# -*- coding: utf-8 -*-
from odoo import models, fields, api


class historiquecandidature(models.Model):
    _name = 'softy.hist'
    _description = 'Historique Candidature'

    nom_etape=fields.Char(string="Nom de l'etape ",required=True)
    evaluator = fields.Many2one('res.users', 'Évaluateur/Recruteur', default=lambda self: self.env.user, required=True)
    date=fields.Date(string="Date de l'etape",required=True)
    notes = fields.Char('Notes/Commentaires')
    applicant_id = fields.Many2one('hr.applicant', 'Candidature', ondelete='cascade')
    
