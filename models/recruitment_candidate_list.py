# -*- coding: utf-8 -*-
from odoo import fields, models, api

class RecruitmentCandidateList(models.Model):
    _name = "recruitment.candidate.list"
    _description = "Liste des Candidats Ajoutés"
    _order = "date_added desc"
   
    # ✅ Main link - only field stored directly
    applicant_id = fields.Many2one('hr.applicant', string="Candidature", required=True, readonly=True, ondelete='cascade')
    
    # ✅ NEW: Link to batch
    batch_id = fields.Many2one(
        'recruitment.candidate.batch',
        string="Lot de Candidatures",
        ondelete='set null',
        tracking=True
    )
   
    # ✅ Metadata fields (stored directly)
    date_added = fields.Datetime(string="Date d'ajout", default=fields.Datetime.now, readonly=True)
    added_by = fields.Many2one('res.users', string="Ajouté par", default=lambda self: self.env.user, readonly=True)
    notes = fields.Text(string="Notes")
   
    # ========== ALL COMPUTED FROM APPLICANT (NO STORE) ==========
   
    # From hr.applicant directly - NO store=True to avoid DB issues
    name = fields.Char(string="Nom du Candidat", related='applicant_id.partner_name', readonly=True)
    email = fields.Char(string="Email", related='applicant_id.email_from', readonly=True)
    phone = fields.Char(string="Téléphone", related='applicant_id.partner_phone', readonly=True)
   
    job_id = fields.Many2one('hr.job', string="Poste (Job)", related='applicant_id.job_id', readonly=True)
    poste = fields.Char(string="Nom du Poste", related='applicant_id.job_id.name', readonly=True)
   
    department_id = fields.Many2one('hr.department', string="Département", related='applicant_id.department_id', readonly=True)
   
    # From hr.candidate (via applicant)
    candidate_id = fields.Many2one('hr.candidate', string="Candidat", related='applicant_id.candidate_id', readonly=True)
   
    # CV/Attachments - get from candidate
    candidate_attachment_ids = fields.One2many('ir.attachment', related='applicant_id.candidate_id.attachment_ids', string="Documents du Candidat", readonly=True)
   
    # First CV attachment (for quick access)
    cv_attachment_id = fields.Many2one('ir.attachment', string="CV Principal", compute='_compute_cv_attachment')
   
    @api.depends('candidate_attachment_ids')
    def _compute_cv_attachment(self):
        """Get the first PDF or any attachment as the main CV"""
        for record in self:
            if record.candidate_attachment_ids:
                # Try to find a PDF first
                pdf_attachment = record.candidate_attachment_ids.filtered(
                    lambda a: a.mimetype == 'application/pdf' or '.pdf' in (a.name or '').lower()
                )
                record.cv_attachment_id = pdf_attachment[0] if pdf_attachment else record.candidate_attachment_ids[0]
            else:
                record.cv_attachment_id = False
   
    def action_view_applicant(self):
        """Smart button to view the applicant record"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Candidature',
            'res_model': 'hr.applicant',
            'res_id': self.applicant_id.id,
            'view_mode': 'form',
            'target': 'current',
        }