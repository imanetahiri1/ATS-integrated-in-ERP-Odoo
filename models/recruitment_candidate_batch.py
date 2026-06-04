# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class RecruitmentCandidateBatch(models.Model):
    _name = "recruitment.candidate.batch"
    _description = "Lot de Candidatures"
    _order = "create_date desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']
   
    name = fields.Char(string="Nom du Lot", required=True, tracking=True)
   
    job_id = fields.Many2one(
        'hr.job',
        string="Poste",
        required=True,
        tracking=True
    )
   
    department_id = fields.Many2one(
        'hr.department',
        string="Département",
        related='job_id.department_id',
        store=True,
        readonly=True
    )
   
    candidate_list_ids = fields.One2many(
        'recruitment.candidate.list',
        'batch_id',
        string="Candidats du Lot"
    )
   
    candidate_count = fields.Integer(
        string="Nombre de Candidats",
        compute='_compute_candidate_count'
    )
   
    create_date = fields.Datetime(string="Date de Création", readonly=True)
    created_by = fields.Many2one(
        'res.users',
        string="Créé par",
        default=lambda self: self.env.user,
        readonly=True
    )
   
    notes = fields.Text(string="Notes / Commentaires")
   
    @api.depends('candidate_list_ids')
    def _compute_candidate_count(self):
        for record in self:
            record.candidate_count = len(record.candidate_list_ids)
   
    def action_view_candidates(self):
        """View all candidates in this batch"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Candidats du Lot'),
            'res_model': 'recruitment.candidate.list',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'context': {'default_batch_id': self.id}
        }
    
    def action_send_batch(self):
        """Placeholder for sending this batch to the client."""
        self.ensure_one()
        # TODO: implement your email / export / API push logic here
        # e.g. generate report, send mail, update state, etc.
        return True