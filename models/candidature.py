# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class HrApplicant(models.Model):
    _inherit = "hr.applicant"
   
    # Your existing fields
    scorecard_ids = fields.One2many(
        comodel_name="softy.scorecard",
        inverse_name="applicant_id",
        string="Scorecard de Recrutement – Entretien RH"
    )
    
    # CHANGED: These are now related fields pointing to candidate_id
    address_domicile = fields.Char(
        string="Address du Domicile",
        related="candidate_id.address_domicile",
        store=True,
        readonly=False
    )
    date_opt = fields.Date(
        string="Date d'obtention du Diplome",
        related="candidate_id.date_opt",
        store=True,
        readonly=False
    )
    etab = fields.Char(
        string="Etablissement",
        related="candidate_id.etab",
        store=True,
        readonly=False
    )
   
    historique_ids = fields.One2many(
        comodel_name="softy.hist",
        inverse_name="applicant_id",
        string="Historique des Etapes de Recrutement"
    )
   
    phone_screening_ids = fields.One2many(
        comodel_name="softy.phone.screening",
        inverse_name="applicant_id",
        string="Screening Telephonique"
    )
   
    sourcer = fields.Many2one(
        comodel_name="res.users",
        string="Sourcer",
    )
   
    is_candidate_blacklisted = fields.Boolean(
        compute="_compute_is_candidate_blacklisted",
        store=True
    )
    
    # NEW FIELDS
    has_multiple_applications = fields.Boolean(
        compute="_compute_candidate_application_status",
        store=True
    )
    
    has_accepted_application = fields.Boolean(
        compute="_compute_candidate_application_status",
        store=True
    )
   
    @api.depends('candidate_id.blacklisted')
    def _compute_is_candidate_blacklisted(self):
        for record in self:
            record.is_candidate_blacklisted = record.candidate_id.blacklisted if record.candidate_id else False
    
    # NEW COMPUTE METHOD
    @api.depends('candidate_id.has_multiple_applications', 'candidate_id.has_accepted_application')
    def _compute_candidate_application_status(self):
        for record in self:
            if record.candidate_id:
                record.has_multiple_applications = record.candidate_id.has_multiple_applications
                record.has_accepted_application = record.candidate_id.has_accepted_application
            else:
                record.has_multiple_applications = False
                record.has_accepted_application = False
   
    def action_add_to_list(self):
        """
        Add candidate to the recruitment list and automatically to a batch for this job
        """
        self.ensure_one()
       
        # ✅ Check if already added to avoid duplicates
        existing = self.env['recruitment.candidate.list'].search([
            ('applicant_id', '=', self.id)
        ], limit=1)
       
        if existing:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Information'),
                    'message': _('Le candidat %s est déjà dans la liste!') % self.partner_name,
                    'type': 'warning',
                    'sticky': False,
                }
            }
       
        # ✅ Find or create a batch for this job
        batch = self.env['recruitment.candidate.batch'].search([
            ('job_id', '=', self.job_id.id),
        ], limit=1, order='create_date desc')
       
        if not batch:
            # Create a new batch
            batch = self.env['recruitment.candidate.batch'].create({
                'name': _('Lot %s - %s') % (self.job_id.name, fields.Date.today().strftime('%B %Y')),
                'job_id': self.job_id.id,
            })
       
        # ✅ Create the candidate list entry and link to batch
        candidate_list = self.env['recruitment.candidate.list'].create({
            'applicant_id': self.id,
            'batch_id': batch.id,
        })
       
        # ✅ Show success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès!'),
                'message': _('Le candidat %s a été ajouté au lot "%s"!') % (self.partner_name, batch.name),
                'type': 'success',
                'sticky': False,
            }
        }