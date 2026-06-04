from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrCandidateInherit(models.Model):
    _inherit = 'hr.candidate'

    # Existing Blacklist Fields
    blacklisted = fields.Boolean(
        string='Blacklisté',
        default=False,
        tracking=True,
        help="Marquer ce candidat comme blacklisté pour empêcher les futures candidatures"
    )
    
    motif_blackliste = fields.Char(
        string='Motif de Blackliste',
        help="Raison pour laquelle le candidat a été blacklisté"
    )

    # New Fields
    address_domicile = fields.Char(string="Address du Domicile")
    date_opt = fields.Date(string="Date d'obtention du Diplome")
    etab = fields.Char(string="Etablissement")
    
    # New Boolean Fields based on application counts
    has_multiple_applications = fields.Boolean(
        string='Multiple Applications',
        compute='_compute_has_multiple_applications',
        store=True,
        help="True if candidate has more than 1 application"
    )

    has_accepted_application = fields.Boolean(
        string='Has Accepted Application',
        compute='_compute_has_accepted_application',
        store=True,
        help="True if candidate has at least one accepted application"
    )
    
    @api.onchange('blacklisted')
    def _onchange_blacklisted(self):
        """Clear the blacklist reason if blacklisted is unchecked"""
        if not self.blacklisted:
            self.motif_blackliste = False

    @api.depends('applicant_ids')
    def _compute_has_multiple_applications(self):
        for candidate in self:
            candidate.has_multiple_applications = len(candidate.applicant_ids) > 1

    @api.depends('applicant_ids', 'applicant_ids.stage_id', 'applicant_ids.stage_id.hired_stage')
    def _compute_has_accepted_application(self):
        for candidate in self:
            candidate.has_accepted_application = any(
                applicant.stage_id.hired_stage for applicant in candidate.applicant_ids
            )